# -*- coding: utf-8 -*-
"""The stepped agent boundary for Monkey Ladder.

Out of Sight next door is a continuous animation the driver clocks
itself. This one is a *preview-then-probe* task, and that is the whole
reason it is wrapped: a round shows a set of tiles, hides them, and asks
for them back. The memory load is one dial -- how many tiles -- and
nothing about the task requires the agent to chain one subgoal into the
next. A capacity measurement taken here cannot be confounded by an
agent's ability to navigate, because there is nothing to navigate.

One tick is one frame, and nothing moves between ticks. The task's own
clock and random stream are replaced by the driver's, so two runs under
the same seed produce the same frames byte for byte.

A trial is one *round*. A round takes several clicks, so unlike the two
tasks already wrapped it opens several action windows -- one per click,
each taking exactly one action and getting its own receipt. The public
outcome is per round, bound to the last receipt of the round and to
every frame in it. That is the one place this boundary generalizes the
contract, and it is written down rather than hidden: many windows, one
outcome, one receipt named by that outcome.

The outcome is read off pixels, never off the task's verdict. Two
frames of the round decide it, both in the archive and both named in
the evidence digests:

- the *preview* frame, where every tile of the set is painted the
  preview colour with its number over it;
- the *result* frame, where tiles the agent got right are painted the
  correct colour -- the same geometry, the same numbers, a different
  fill -- and a tile it got wrong is painted the wrong colour.

So a round is correct exactly when the result frame holds no
wrong-colour pixels and its correct-colour count equals the preview
frame's preview-colour count. The second half is what makes a forged
outcome hard: it is not enough for a frame to lack the wrong colour, it
has to carry the whole set. Counting those pixels also recovers the set
size, so a third party can score capacity without being told it.

There are no cell ids, no sequence, no phase names and no answer key in
the observation. Actions are opaque integer ports.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
from typing import (Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple,
                    Union)

import pyglet

from .accounting import Accounting
from .export import FrameExport
from .frames import capture_rgba, digest_rgba, now_ns
from .outcome import PUBLIC_OUTCOME_KEYS

Ports = Union[None, int, Mapping[int, bool], Iterable[int]]

#: The rate the task is clocked at. The task's deadlines are in
#: seconds, and the driver counts them in ticks rather than sleeping
#: through them, so the seconds mean the same thing at any rate.
DEFAULT_FRAME_HZ = 60.0

#: Below this a stray run of matching bytes is not a verdict. One tile
#: is a flat fill of several thousand pixels at the smallest window the
#: program allows, so the floor is nowhere near a real tile.
FEWEST_VERDICT_PIXELS = 200

#: A round is scored when the tiles the agent placed cover the same
#: pixels the preview did. Anti-aliased digits sit over both, in the
#: same places, so the two counts agree exactly on a clean round; this
#: allows for a handful of bytes of slack rather than demanding it.
SET_MATCH_SLACK = 64


def _tile_colors() -> Tuple[Tuple[int, int, int], Tuple[int, int, int],
                            Tuple[int, int, int]]:
    """The preview, correct and wrong fills, read from the task."""
    return (64, 96, 255), (46, 170, 92), (220, 64, 64)


def _count_fill(rgba: bytes, color: Tuple[int, int, int]) -> int:
    """How many opaque pixels of the frame are exactly *color*.

    An exact four-byte match, so the whole frame can be counted at C
    speed instead of a python loop over a million pixels. A run that
    straddles a pixel boundary would need those exact three bytes and
    an opaque alpha in that order; it cannot move a tally that is zero.
    """
    return rgba.count(bytes(color) + b'\xff')


def derive_ladder_outcome(rgba: bytes, width: int, height: int,
                          evidence_digests: Any, receipt_id: Optional[int],
                          preview_rgba: Optional[bytes] = None,
                          frame_seq: Optional[int] = None,
                          timestamp_ns: Optional[int] = None,
                          neutral: bool = False
                          ) -> Optional[Dict[str, Any]]:
    """The scalar for one round, read off two frames of that round.

    ``-1.0`` when the result frame carries the wrong colour at all, and
    ``+1.0`` when it carries none of it and its correct-colour count
    matches the preview frame's. Anything else -- a frame mid-round, a
    result frame that does not cover the set -- yields ``None``, which
    is not the same as zero: it means there is nothing owed yet.

    ``neutral`` scores those mid-round frames ``0.0`` instead of
    ``None``. A runtime that pairs one outcome to one action needs a
    verdict for every action, and a tile placed part-way through a round
    is owed exactly nothing; the rule for a positive is untouched, so a
    round still cannot be scored well without covering the whole set.

    The payload carries no pixel counts. Those would say how large the
    set was and how big the window is; the scalar says only what the
    learner is owed.
    """
    del width, height                  # the whole frame is searched
    if not rgba:
        return None
    preview, correct, wrong = _tile_colors()
    n_wrong = _count_fill(rgba, wrong)
    if n_wrong >= FEWEST_VERDICT_PIXELS:
        scalar = -1.0
    else:
        n_correct = _count_fill(rgba, correct)
        n_preview = (_count_fill(preview_rgba, preview)
                     if preview_rgba else 0)
        resolved = (
            n_preview >= FEWEST_VERDICT_PIXELS
            and abs(n_correct - n_preview) <= SET_MATCH_SLACK
        )
        if not resolved:
            if not neutral:
                return None            # the set is not all there yet
            scalar = 0.0
        else:
            scalar = 1.0
    outcome: Dict[str, Any] = {
        'scalar': scalar,
        'evidence_digests': list(evidence_digests),
        'receipt_id': receipt_id,
    }
    if frame_seq is not None:
        outcome['frame_seq'] = frame_seq
    if timestamp_ns is not None:
        outcome['timestamp_ns'] = timestamp_ns
    return outcome


def verify_ladder_outcome(outcome: Optional[Mapping[str, Any]], rgba: bytes,
                          width: int, height: int,
                          archive: Optional[Mapping[str, bytes]] = None,
                          receipt_ledger: Optional[Mapping[int, Any]] = None
                          ) -> bool:
    """The learner-facing verifier for this task's outcomes.

    Every rule the n-back verifier applies applies here too: it fails
    closed without both the frame archive and the receipt ledger, and
    the receipt must be bound to this round's evidence. What differs is
    that scoring a round needs the round's preview frame as well as its
    result frame, so the preview is looked up in the archive by the
    first evidence digest -- which means a verifier holding a partial
    archive fails closed rather than guessing.
    """
    from .outcome import verify_public_outcome

    digests = list((outcome or {}).get('evidence_digests') or ())
    preview = None
    if archive and digests:
        preview = archive.get(digests[0])
    if preview is None and (outcome or {}).get('scalar', 0.0) > 0.0:
        return False

    def derive(frame: bytes, w: int, h: int, evidence: Any,
               receipt_id: Optional[int], frame_seq: Optional[int] = None,
               timestamp_ns: Optional[int] = None
               ) -> Optional[Dict[str, Any]]:
        return derive_ladder_outcome(
            frame, w, h, evidence, receipt_id, preview_rgba=preview,
            frame_seq=frame_seq, timestamp_ns=timestamp_ns)

    return verify_public_outcome(outcome, rgba, width, height, archive,
                                 receipt_ledger, derive=derive)


class MonkeyLadderEnv:
    """Deterministic, stepped view of one Monkey Ladder run.

    Constructor arguments own the dials, so a learner never reaches
    into ``cfg``; they survive :meth:`reset`.
    """

    def __init__(self, seed: Optional[int] = None,
                 shm_name: Optional[str] = None,
                 grid: Optional[int] = None,
                 level: Optional[int] = None,
                 show_ms: Optional[int] = None,
                 per_tile_ms: Optional[int] = None,
                 rounds: int = 20,
                 adaptive: bool = False,
                 cursor: bool = False,
                 neutral_outcomes: bool = False,
                 frame_hz: float = DEFAULT_FRAME_HZ,
                 visible: bool = False) -> None:
        self._asked = {
            'MONKEY_LADDER_GRID': grid,
            'MONKEY_LADDER_START_LENGTH': level,
            'MONKEY_LADDER_SHOW_MS': show_ms,
            'MONKEY_LADDER_PER_TILE_MS': per_tile_ms,
        }
        # Off by default: a curriculum that moves under the learner is
        # the runtime's business, not the task's. A capacity sweep in
        # particular needs the set size pinned.
        self._adaptive = bool(adaptive)
        # Two interfaces onto the same task. By default a port names a
        # tile outright, which is the cleanest thing to measure capacity
        # through: one action per item, no motor cost in between. With
        # ``cursor`` the ports are four moves and a commit, five in all,
        # which is what a runtime built around a five-action decoder can
        # drive without being rebuilt. The recall is the same either way;
        # what differs is how many actions it costs to express.
        self._cursor = bool(cursor)
        # One outcome per action rather than one per round, the extra
        # ones worth nothing. A runtime that expects a verdict for every
        # action it takes needs this; a caller reading the task's own
        # contract does not, and gets one outcome per round.
        self._neutral_outcomes = bool(neutral_outcomes)
        self._rounds = int(rounds)
        if self._rounds < 1:
            raise ValueError('a run needs at least one round')
        self._visible = bool(visible)
        self._hz = float(frame_hz)
        if self._hz <= 0.0:
            raise ValueError('frame_hz must be positive')
        self._dt = 1. / self._hz

        self._export = FrameExport(
            shm_name=shm_name or os.environ.get('NW_SHM'))
        self.accounting = Accounting()
        self.task: Any = None
        self._virtual_now = 0.0

        # Frame state.
        self._seq = 0
        self._timestamp_ns = 0
        self._width = 0
        self._height = 0
        self._rgba = b''
        self._digest = ''
        self._pending = False
        self._consumed = True
        self._done = False

        # Round state.
        self._round = 0
        self._round_digests: List[str] = []
        self._preview_rgba: Optional[bytes] = None
        self._receipt: Optional[Dict[str, Any]] = None
        self._response_open = False
        self._receipt_seq = 0
        self._action_finalized = False
        self._outcome_owed = False
        self._receipt_ledger: Dict[int, Dict[str, Any]] = {}
        self._archive: Dict[str, bytes] = {}
        self._events: List[Dict[str, Any]] = []
        self._delivered: Set[Any] = set()
        self._cached_outcome: Optional[Dict[str, Any]] = None

        self._closed = False
        self.reset(0 if seed is None else seed)

    # --- public API -------------------------------------------------------

    #: Four moves and a commit. Which port is which is not said here.
    CURSOR_ACTION_COUNT = 5

    @property
    def n_actions(self) -> int:
        """How many opaque action ports this task offers."""
        if self._cursor:
            return self.CURSOR_ACTION_COUNT
        return int(self.task.grid) ** 2

    def reset(self, seed: int = 0) -> Dict[str, Any]:
        """Start a fresh run under *seed* and return the first frame."""
        from neural_workshop import display, state
        from neural_workshop.ui.monkeyladder import MonkeyLadder

        seed = int(seed)
        random.seed(seed)
        if self.task is not None:
            self.task.close()
            self.task = None
        for screen in display.open_overlays():
            try:
                screen.close()
            except Exception:
                display.unregister_overlay(screen)
        try:
            state.window.set_visible(self._visible)
        except Exception:
            pass

        task = MonkeyLadder()
        # Nothing may advance behind the driver's back, and no deadline
        # in the task may be read off a clock the driver does not own.
        pyglet.clock.unschedule(task.update)
        self._virtual_now = 0.0
        task.clock = lambda: self._virtual_now
        task.rng = random.Random(seed)
        self._apply_dials(task)
        self.task = task

        self._clear_run_state()
        task.start_round()
        self._publish()
        return self.observe()

    def observe(self) -> Dict[str, Any]:
        """The current frame.

        The framebuffer may be re-read as often as wanted; the outcome
        is drain-once and disappears after the first observation.
        """
        obs = self._observation()
        self._cached_outcome = None
        self._consumed = True
        self._pending = False
        self._export.write(self._seq, self._timestamp_ns, self._width,
                           self._height, self._rgba, True)
        return obs

    def act(self, ports: Ports = None,
            logp: Optional[float] = None) -> Dict[str, Any]:
        """Place one tile. At most one per action window.

        *logp* is an optional policy log-propensity stored on the
        receipt so a runtime can map it back to this click; it is not
        interpreted here. Returns a receipt, or a rejection when the
        task is not taking clicks or one was already given this window.
        """
        rejected = {
            'ok': False, 'receipt_id': None, 'frame_seq': self._seq,
            'timestamp_ns': now_ns(), 'ports': (), 'logp': None,
        }
        if not self._response_open or self._receipt is None:
            return rejected
        if self._action_finalized:
            return rejected
        indices = self._decode_ports(ports)
        if len(indices) != 1:
            # One port is one tile, so naming several is not a click
            # and naming none is not one either.
            return rejected
        index = int(indices[0])
        if not 0 <= index < self.n_actions:
            return rejected

        if self._cursor:
            self._drive_cursor(index)
        else:
            grid = int(self.task.grid)
            self.task.click_cell((index // grid, index % grid))
        self._action_finalized = True
        self._outcome_owed = True

        held = self._receipt
        self._receipt = {
            'ok': True,
            'receipt_id': held['receipt_id'],
            'trial_seq': held.get('trial_seq', held['receipt_id']),
            'frame_seq': held['frame_seq'],
            'timestamp_ns': now_ns(),
            'ports': tuple(indices),
            'logp': logp,
            'stimulus_digest': held.get('stimulus_digest'),
            'window_open_ns': held.get('window_open_ns'),
        }
        self._receipt_ledger[self._receipt['receipt_id']] = dict(self._receipt)
        return dict(self._receipt)

    def advance(self) -> Dict[str, Any]:
        """Tick the task once and return the frame it drew."""
        if self._pending and not self._consumed:
            self.accounting.duplicate_frames += 1
            return self.observe()
        if self._done:
            return self.observe()

        self._virtual_now += self._dt
        self.task.update(self._dt)
        self._publish()
        return self.observe()

    def step(self, ports: Ports = None
             ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
        """Act (if given ports), advance, and drain the pending events."""
        if ports is not None:
            self.act(ports)
        obs = self.advance()
        events = list(self._events)
        self._events = []
        return obs, events, bool(obs.get('done'))

    def close(self) -> None:
        """Shut the task down and release the export block."""
        if self._closed:
            return
        self._closed = True
        if self.task is not None:
            try:
                self.task.close()
            except Exception:
                pass
            self.task = None
        self._export.close()

    # --- setup ------------------------------------------------------------

    def _dial(self, key: str) -> int:
        """One dial: what was asked for, or what the task ships with.

        Deliberately not what the config holds. A player who has been
        turning the task's own dials up must not quietly change what a
        run under a given seed means, so the fallback is the value in
        the source, and the only other way in is this constructor.
        """
        from neural_workshop.config import shipped_defaults
        asked = self._asked.get(key)
        if asked is None:
            asked = shipped_defaults()[key]
        value = int(asked)
        if value < 0:
            raise ValueError('%s cannot be negative' % key)
        return value

    def _apply_dials(self, task: Any) -> None:
        """Push the run's knobs into the task it just built."""
        task.grid = self._dial('MONKEY_LADDER_GRID')
        task.show_ms = self._dial('MONKEY_LADDER_SHOW_MS')
        task.per_tile_ms = self._dial('MONKEY_LADDER_PER_TILE_MS')
        task.adaptive = self._adaptive
        task.cursor_enabled = self._cursor
        # The result frame has to paint the same geometry the preview
        # did, numbers and all, or the two counts cannot be compared.
        task.reveal_answer = True
        level = self._dial('MONKEY_LADDER_START_LENGTH')
        task.start_level = level
        task.level = min(max(2, level), task.grid * task.grid)
        task._layout_grid()
        task._redraw()

    def _clear_run_state(self) -> None:
        self.accounting.reset()
        self._events = []
        self._round = 0
        self._round_digests = []
        self._preview_rgba = None
        self._receipt = None
        self._response_open = False
        self._receipt_seq = 0
        self._pending = False
        self._consumed = True
        self._archive = {}
        self._action_finalized = False
        self._outcome_owed = False
        self._delivered = set()
        self._cached_outcome = None
        self._receipt_ledger = {}
        self._seq = 0
        self._done = False

    # --- windows ----------------------------------------------------------

    def _open_window(self) -> None:
        """Open one click's action window and pre-register its receipt."""
        self._receipt_seq += 1
        self._action_finalized = False
        self._response_open = True
        self._receipt = {
            'ok': True,
            'receipt_id': self._receipt_seq,
            'trial_seq': self._round,
            'frame_seq': self._seq,
            'timestamp_ns': now_ns(),
            'ports': (),
            'logp': None,
            'stimulus_digest': self._digest,
            'window_open_ns': now_ns(),
        }
        self.accounting.logical_trials += 1

    #: Port index to cursor step. The fifth port commits.
    _CURSOR_STEPS = ((1, 0), (-1, 0), (0, -1), (0, 1))

    def _drive_cursor(self, index: int) -> None:
        """One move, or the commit."""
        if index < len(self._CURSOR_STEPS):
            self.task.move_cursor(*self._CURSOR_STEPS[index])
            return
        self.task.commit_cursor()

    def _decode_ports(self, ports: Ports) -> List[int]:
        if ports is None:
            return []
        if isinstance(ports, int):
            return [int(ports)]
        if isinstance(ports, Mapping):
            return [int(k) for k, v in ports.items() if v]
        return [int(p) for p in ports]

    def _emit_once(self, key: Any, event: Dict[str, Any]) -> bool:
        """Queue *event* unless something with this key already went out."""
        if key in self._delivered:
            return False
        self._delivered.add(key)
        self._events.append(event)
        return True

    def _publish_outcome(self, neutral: bool = False) -> None:
        """Derive and emit the public outcome for a finished round."""
        receipt_id = (self._receipt or {}).get('receipt_id')
        key = ('outcome', self._round, receipt_id)
        if key in self._delivered:
            return
        outcome = derive_ladder_outcome(
            self._rgba, self._width, self._height, self._round_digests,
            receipt_id, preview_rgba=self._preview_rgba, frame_seq=self._seq,
            timestamp_ns=self._timestamp_ns, neutral=neutral)
        if outcome is None:
            return                     # the round has not resolved yet
        public = {k: outcome[k] for k in PUBLIC_OUTCOME_KEYS if k in outcome}
        self._cached_outcome = public
        self.accounting.authenticated_outcomes.add((
            public['receipt_id'], tuple(public['evidence_digests']),
            public['scalar']))
        emitted = self._emit_once(key, {
            'type': 'outcome',
            'scalar': public['scalar'],
            'evidence_digests': public['evidence_digests'],
            'receipt_id': public['receipt_id'],
            'frame_seq': public['frame_seq'],
            'timestamp_ns': public['timestamp_ns'],
        })
        if emitted and self._receipt:
            self.accounting.action_to_outcome_ns.append(
                self._timestamp_ns - self._receipt['timestamp_ns'])

    # --- frames -----------------------------------------------------------

    def _observation(self) -> Dict[str, Any]:
        obs: Dict[str, Any] = {
            'frame_seq': self._seq,
            'timestamp_ns': self._timestamp_ns,
            'width': self._width,
            'height': self._height,
            'rgba': self._rgba,
            'done': self._done,
        }
        if self._cached_outcome is not None:
            obs['outcome'] = self._cached_outcome
        return obs

    def _publish(self) -> None:
        """Draw one frame and everything that follows from it."""
        from neural_workshop import state
        if self._pending and not self._consumed:
            self.accounting.dropped_frames += 1

        window = state.window
        window.switch_to()
        window.dispatch_events()
        self.task.on_draw()
        width, height, rgba = capture_rgba(window)
        window.flip()

        self._seq += 1
        self._timestamp_ns = now_ns()
        self._width, self._height, self._rgba = width, height, rgba
        self._digest = digest_rgba(rgba)
        self._archive[self._digest] = bytes(rgba)
        self._pending = True
        self._consumed = False
        self.accounting.significant_frames += 1
        self._export.write(self._seq, self._timestamp_ns, width, height,
                           rgba, False)
        self._cached_outcome = None

        phase = self.task.phase
        self._round_digests.append(self._digest)
        if self._neutral_outcomes and self._outcome_owed:
            self._outcome_owed = False
            self._publish_outcome(neutral=phase != 'result')
        if phase == 'show':
            # Every preview frame paints the whole set, so the last one
            # is as good as the first and is what the result is scored
            # against; keeping the newest costs nothing.
            self._preview_rgba = bytes(rgba)
        elif phase == 'input':
            # One window per click: the window that just took an action
            # closes with the frame that shows its result, and the next
            # tile's window opens on the same frame.
            if self._action_finalized or not self._response_open:
                self._open_window()
        elif phase == 'result':
            self._response_open = False
            if not self._neutral_outcomes:
                self._publish_outcome()
            self._finish_round()

    def _finish_round(self) -> None:
        """Close out a scored round and start the next, or end the run."""
        key = ('round', self._round)
        if key in self._delivered:
            return
        self._delivered.add(key)
        self._round += 1
        if self._round >= self._rounds:
            self._done = True
            self._emit_once(('run_end',), {
                'type': 'run_end',
                'frame_seq': self._seq,
                'timestamp_ns': self._timestamp_ns,
            })
            return
        self._round_digests = []
        self._preview_rgba = None
        self._receipt = None
        self.task.start_round()


def make_ladder_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> MonkeyLadderEnv:
    """A production environment: the task's own defaults, no adaptation."""
    return MonkeyLadderEnv(seed=seed, shm_name=shm_name)
