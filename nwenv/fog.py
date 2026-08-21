# -*- coding: utf-8 -*-
"""The stepped agent boundary for Fog of War.

Monkey Ladder next door is preview-then-probe and Out of Sight is a
continuous animation. This one is neither: it is a *world*, and the
only thing to do in it is go somewhere. A tick is a move, nothing
happens between moves, and the run is over when the move budget is.

What makes it worth wrapping separately is what the scalar is read
off. There is no verdict painted anywhere — no right, no wrong, no
tiles turning green. The frame shows a patch of lit ground in a field
of black, and the only quantity in it is *how much ground is lit*. So
the outcome is the difference between two frames of the same world:

    +1.0 when the lit ground grew, 0.0 when it did not.

That is derivable by a third party holding nothing but the frame
archive: count the floor pixels and the walker's pixels in the frame
before the move and in the frame after it, and compare. No cell ids,
no coordinates, no coverage number, nothing from inside the task. The
walker's own pixels are counted along with the floor on purpose —
without them the count would dip every time the walker stepped onto
newly-lit ground and covered part of it, and the measure has to be
about the ground rather than about where the walker is standing on it.

**There is deliberately no negative.** Walking into a wall pays zero
and costs a move, and that is the whole of its consequence: the screen
does not change by so much as a byte, so a bump is not merely
unrewarded, it is invisible. That is the one property this boundary
exists to guarantee, and :mod:`tests.test_env_fog` checks it by
bumping and comparing frame digests. An earlier instrument elsewhere
paid an agent for wall-bumping because bumps were cheap spectacle;
here there is no spectacle to be had without travelling.

Measured on the shipped world at 1824x1368: a move that lights new
ground gains at least 4032 pixels, and a move that lights none moves
the count by 0. The threshold below sits two orders of magnitude
inside that gap.

Actions are five opaque integer ports — stay, and four ways. Which
port is which is not said here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
from typing import (Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple,
                    Union)

from .accounting import Accounting
from .export import FrameExport
from .frames import capture_rgba, digest_rgba, now_ns
from .outcome import PUBLIC_OUTCOME_KEYS

Ports = Union[None, int, Mapping[int, bool], Iterable[int]]

#: The rate the task is clocked at. Nothing in this task is timed, so
#: the rate only names what a tick is worth; it is kept so that a
#: driver can hold every boundary to the same shape.
DEFAULT_FRAME_HZ = 60.0

#: How much brighter a frame has to be than the one before it to count
#: as having found new ground. One cell is worth several thousand
#: pixels at any window the program allows, and a move that finds
#: nothing moves the count by nothing, so this is far inside the gap
#: rather than tuned to the edge of it. It exists to absorb the single
#: pixel of overlap between neighbouring cells, which can shave a cell
#: edge off the tally when a newly lit wall abuts already-lit floor.
NEW_GROUND_PIXELS = 200

#: Stay, and four ways. The runtime's decoder is built around this
#: width; see ``runtime_ports`` for driving it from a wider one.
FOG_ACTION_COUNT = 5


def _world_colors() -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """The floor and walker fills, read from the task."""
    from neural_workshop.ui.fogofwar import FLOOR, WALKER
    return FLOOR, WALKER


def _count_fill(rgba: bytes, color: Tuple[int, int, int]) -> int:
    """How many opaque pixels of the frame are exactly *color*.

    An exact four-byte match, so a whole frame is counted at C speed
    rather than in a python loop over two million pixels.
    """
    return rgba.count(bytes(color) + b'\xff')


def lit_pixels(rgba: bytes) -> int:
    """How much ground the frame shows lit.

    Floor plus walker, because the walker stands on floor and hides
    some of it. Counting the pair makes the number depend on what has
    been revealed and not at all on where the walker happens to be,
    which is what lets one move be compared with the next.
    """
    floor, walker = _world_colors()
    return _count_fill(rgba, floor) + _count_fill(rgba, walker)


def derive_fog_outcome(rgba: bytes, width: int, height: int,
                       evidence_digests: Any, receipt_id: Optional[int],
                       before_rgba: Optional[bytes] = None,
                       frame_seq: Optional[int] = None,
                       timestamp_ns: Optional[int] = None,
                       neutral: bool = False) -> Optional[Dict[str, Any]]:
    """The scalar for one move, read off the frames either side of it.

    ``+1.0`` when this frame shows more lit ground than the frame
    before it did. Otherwise ``None`` — which is not zero, it means
    there is nothing owed — or ``0.0`` when *neutral*, for a runtime
    that pairs one outcome to every action it takes.

    Without *before_rgba* there is nothing to compare against and the
    answer is ``None`` whatever *neutral* says, because a claim that
    ground was found cannot be checked against a frame nobody holds.
    That is the fail-closed case, and it is what stops the first frame
    of a world from being scored.

    The payload carries no pixel counts. Those would say how large the
    world is and how much of it is left; the scalar says only what the
    move was worth.
    """
    del width, height                  # the whole frame is counted
    if not rgba or before_rgba is None:
        return None
    grew = lit_pixels(rgba) - lit_pixels(before_rgba)
    if grew >= NEW_GROUND_PIXELS:
        scalar = 1.0
    elif neutral:
        scalar = 0.0
    else:
        return None
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


def verify_fog_outcome(outcome: Optional[Mapping[str, Any]], rgba: bytes,
                       width: int, height: int,
                       archive: Optional[Mapping[str, bytes]] = None,
                       receipt_ledger: Optional[Mapping[int, Any]] = None
                       ) -> bool:
    """The learner-facing verifier for this task's outcomes.

    Every rule the other boundaries apply applies here: it fails closed
    without both the frame archive and the receipt ledger, and the
    receipt must be bound to this move's evidence. What differs is that
    scoring a move needs the frame *before* it as well as the frame
    after, so the earlier one is looked up in the archive by the first
    evidence digest — which means a verifier holding a partial archive
    fails closed rather than guessing.

    A zero is checked by the same reader as a one. That concedes
    nothing: a claim worth something still has to survive the pixel
    test, and a forged nothing is still nothing.
    """
    from .outcome import verify_public_outcome

    digests = list((outcome or {}).get('evidence_digests') or ())
    before = archive.get(digests[0]) if (archive and digests) else None
    if before is None:
        return False

    def derive(frame: bytes, w: int, h: int, evidence: Any,
               receipt_id: Optional[int], frame_seq: Optional[int] = None,
               timestamp_ns: Optional[int] = None
               ) -> Optional[Dict[str, Any]]:
        return derive_fog_outcome(
            frame, w, h, evidence, receipt_id, before_rgba=before,
            frame_seq=frame_seq, timestamp_ns=timestamp_ns, neutral=True)

    return verify_public_outcome(outcome, rgba, width, height, archive,
                                 receipt_ledger, derive=derive)


class FogOfWarEnv:
    """Deterministic, stepped view of one Fog of War run.

    Constructor arguments own the dials, so a learner never reaches
    into ``cfg``; they survive :meth:`reset`.
    """

    def __init__(self, seed: Optional[int] = None,
                 shm_name: Optional[str] = None,
                 radius: Optional[int] = None,
                 moves: Optional[int] = None,
                 worlds: int = 3,
                 persist_revealed: bool = True,
                 cursor: bool = False,
                 neutral_outcomes: bool = False,
                 runtime_ports: int = 0,
                 round_tick_limit: int = 0,
                 frame_hz: float = DEFAULT_FRAME_HZ,
                 visible: bool = False) -> None:
        self._asked = {
            'FOG_RADIUS': radius,
            'FOG_MOVES': moves,
        }
        del cursor                     # one interface only; kept for shape
        # With the map on, ground stays lit and the lit count only ever
        # climbs, which is what makes the frame difference a coverage
        # measure. With it off the lit patch merely follows the walker
        # about, and a positive says "the patch is bigger than it was"
        # rather than "there is new ground" -- still honest about the
        # pixels, but no longer a measure of exploring. Said here
        # because a run configured that way should be read that way.
        self._persist = bool(persist_revealed)
        # One outcome per action rather than only for the moves that
        # found something. A runtime that expects a verdict for every
        # action it takes needs this; a caller reading the task's own
        # contract does not, and hears only about the moves that paid.
        self._neutral_outcomes = bool(neutral_outcomes)
        # A wider decoder can drive this task: the ports past the fifth
        # do nothing at all, which is what "stay" already does. Never
        # narrower, because dropping a way to walk would change the
        # task rather than the interface.
        self._runtime_ports = int(runtime_ports)
        if self._runtime_ports and self._runtime_ports < FOG_ACTION_COUNT:
            raise ValueError('a fog runtime needs at least %d ports'
                             % FOG_ACTION_COUNT)
        # A world ends on its move budget, but a driver may want it
        # bounded in ticks as well -- an agent that only ever chooses
        # "stay" spends no moves and would otherwise sit there for ever.
        self._round_tick_limit = int(round_tick_limit)
        if self._round_tick_limit < 0:
            raise ValueError('a round tick limit cannot be negative')
        self._round_ticks = 0
        self._round_timeouts = 0
        self._worlds = int(worlds)
        if self._worlds < 1:
            raise ValueError('a run needs at least one world')
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

        # Move state.
        self._round = 0
        self._before_rgba: Optional[bytes] = None
        self._before_digest = ''
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

        # Driver-side instruments. Never in an observation; they exist
        # so a broken world is caught before experiments are run in it.
        self._attempts = 0
        self._moved = 0
        self._bumped = 0

        self._closed = False
        self.reset(0 if seed is None else seed)

    # --- public API -------------------------------------------------------

    @property
    def n_actions(self) -> int:
        """How many opaque action ports this task offers."""
        return max(FOG_ACTION_COUNT, self._runtime_ports)

    def reset(self, seed: int = 0) -> Dict[str, Any]:
        """Start a fresh run under *seed* and return the first frame."""
        from neural_workshop import display, state
        from neural_workshop.ui.fogofwar import FogOfWar

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

        task = FogOfWar(persist_revealed=self._persist)
        # Nothing may advance behind the driver's back, and no deadline
        # in the task may be read off a clock the driver does not own.
        self._virtual_now = 0.0
        task.clock = lambda: self._virtual_now
        task.rng = random.Random(seed)
        self._apply_dials(task)
        self.task = task

        self._clear_run_state()
        task.start_run()
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
        """Take one move. At most one per action window.

        *logp* is an optional policy log-propensity stored on the
        receipt so a runtime can map it back to this move; it is not
        interpreted here. Returns a receipt, or a rejection when the
        world is not taking moves or one was already given this window.
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
            # One port is one move, so naming several is not a move and
            # naming none is not one either.
            return rejected
        index = int(indices[0])
        if not 0 <= index < self.n_actions:
            return rejected

        self._walk(index)
        self._action_finalized = True
        self._outcome_owed = True
        # The frame this move is answerable against is the one that was
        # up when it was taken.
        self._before_rgba = bytes(self._rgba)
        self._before_digest = self._digest

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
        self._round_ticks += 1
        if (self._round_tick_limit
                and self._round_ticks >= self._round_tick_limit
                and self.task.phase == 'exploring'):
            self._round_timeouts += 1
            self.task.end_world()
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

    def mobility(self) -> Dict[str, Any]:
        """Driver-side proof that the walker can actually get about.

        Never part of an observation, and not something a learner can
        read. It is an instrument: an avatar sealed into a cell, or
        stood somewhere off the drawn surface, looks from the outside
        exactly like an agent that has not learned to explore, and the
        difference is worth being able to tell cheaply. ``move_rate``
        near zero over a run that attempted plenty of moves means the
        world is at fault, not the policy.
        """
        return {
            'attempts': self._attempts,
            'moved': self._moved,
            'bumped': self._bumped,
            'move_rate': (self._moved / float(self._attempts)
                          if self._attempts else 0.0),
            'cells_walked': len(getattr(self.task, 'walked', ()) or ()),
        }

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
        task.radius = self._dial('FOG_RADIUS')
        task.moves_allowed = self._dial('FOG_MOVES')
        task.total_trials = self._worlds
        task.persist = self._persist

    def _clear_run_state(self) -> None:
        self.accounting.reset()
        self._events = []
        self._round = 0
        self._round_ticks = 0
        self._round_timeouts = 0
        self._before_rgba = None
        self._before_digest = ''
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
        self._attempts = 0
        self._moved = 0
        self._bumped = 0
        self._seq = 0
        self._done = False

    # --- moves ------------------------------------------------------------

    def _walk(self, index: int) -> None:
        """Drive one port. Ports past the fourth way are a stay."""
        from neural_workshop.ui.fogofwar import STEPS
        self._attempts += 1
        if index >= len(STEPS):
            return                     # a wider decoder's spare port
        dx, dy = STEPS[index]
        if not (dx or dy):
            return                     # stay: spends no move, sees no more
        if self.task.step(dx, dy):
            self._moved += 1
        else:
            self._bumped += 1

    def _open_window(self) -> None:
        """Open one move's action window and pre-register its receipt."""
        self._receipt_seq += 1
        self._action_finalized = False
        self._response_open = True
        self._receipt = {
            'ok': True,
            'receipt_id': self._receipt_seq,
            'trial_seq': self._receipt_seq,
            'frame_seq': self._seq,
            'timestamp_ns': now_ns(),
            'ports': (),
            'logp': None,
            'stimulus_digest': self._digest,
            'window_open_ns': now_ns(),
        }
        self.accounting.logical_trials += 1

    def _decode_ports(self, ports: Ports) -> List[int]:
        if ports is None:
            return []
        if isinstance(ports, int):
            return [int(ports)]
        if isinstance(ports, Mapping):
            return [int(k) for k, v in ports.items() if v]
        return [int(p) for p in ports]

    def _bind_receipt_to_move(self, receipt_id: Optional[int],
                              evidence: List[str]) -> None:
        """Record which frames this receipt answers for.

        A window opens on whatever frame is up, and what the move is
        answerable against is the pair either side of it. Binding says
        so, so a verifier can check the pair it was handed really
        belongs to this receipt.
        """
        if receipt_id is None or receipt_id not in self._receipt_ledger:
            return
        bound = self._receipt_ledger[receipt_id]
        bound['stimulus_digest'] = evidence[0]
        bound['evidence_digests'] = list(evidence)
        bound['feedback_digest'] = self._digest
        bound['feedback_frame_seq'] = self._seq

    def _emit_once(self, key: Any, event: Dict[str, Any]) -> bool:
        """Queue *event* unless something with this key already went out."""
        if key in self._delivered:
            return False
        self._delivered.add(key)
        self._events.append(event)
        return True

    def _publish_outcome(self) -> None:
        """Derive and emit the public outcome for the move just taken."""
        receipt_id = (self._receipt or {}).get('receipt_id')
        key = ('outcome', receipt_id)
        if key in self._delivered or self._before_rgba is None:
            return
        evidence = [self._before_digest, self._digest]
        self._bind_receipt_to_move(receipt_id, evidence)
        outcome = derive_fog_outcome(
            self._rgba, self._width, self._height, evidence, receipt_id,
            before_rgba=self._before_rgba, frame_seq=self._seq,
            timestamp_ns=self._timestamp_ns, neutral=self._neutral_outcomes)
        if outcome is None:
            return                     # nothing found, and nothing owed
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

        if self._outcome_owed:
            self._outcome_owed = False
            self._publish_outcome()
        if self.task.phase == 'finished':
            self._finish_world()
        if not self._done and (self._action_finalized
                               or not self._response_open):
            self._open_window()

    def _finish_world(self) -> None:
        """Close out a finished world and start the next, or end the run."""
        key = ('world', self._round)
        if key in self._delivered:
            return
        self._delivered.add(key)
        self._round += 1
        if self._round >= self._worlds:
            self._done = True
            self._response_open = False
            self._emit_once(('run_end',), {
                'type': 'run_end',
                'frame_seq': self._seq,
                'timestamp_ns': self._timestamp_ns,
            })
            return
        self._round_ticks = 0
        self._before_rgba = None
        self.task._next_trial()


def make_fog_env(seed: int = 0,
                 shm_name: Optional[str] = None) -> FogOfWarEnv:
    """A production environment: the task's own defaults, map kept."""
    return FogOfWarEnv(seed=seed, shm_name=shm_name)
