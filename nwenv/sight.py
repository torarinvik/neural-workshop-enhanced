# -*- coding: utf-8 -*-
"""The stepped agent boundary for Out of Sight.

The n-back environment next door watches a game it does not control and
has to work out where one trial ends and the next begins. This one is
the other way round: the task is a continuous animation, so the driver
owns its clock outright and one step is one tick of it. Nothing moves
between steps, and two runs under the same seed produce the same frames
byte for byte.

One tick is one frame. A tick renders, and the learner sees pixels —
the same picture a person plays against, minus nothing and plus
nothing. There are no dot positions, no velocities, no target flags, no
phase names in the observation, and no answer key anywhere in it.

A trial is one *question*: the window opens on the tick a dot is ringed
and closes when the ring resolves. Exactly one action may be finalized
inside it and that action gets a receipt, exactly as in the n-back
environment. Two opaque ports, and which is which is not said here.

The public outcome is derived from pixels alone: the ring turns one of
two colours when a question resolves, and the scalar is +1 or -1
according to which. Counting ring pixels rather than reading the task's
own verdict is the point — a third party holding the frame archive and
the receipt ledger can re-derive every outcome without being trusted
with the game.

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

#: The window the task is driven at, and the tick that goes with it.
#: Sixty is what a person plays against; a learner that wants less can
#: ask for it, and the task's seconds stay the task's seconds either
#: way because the clock is counted in ticks, not slept through.
DEFAULT_FRAME_HZ = 60.0

#: The slowest the task may be clocked. The task clamps how far one
#: call may move the flock, so that a hitch in real-time play cannot
#: teleport a dot; below this rate that clamp would bite, the motion
#: would fall behind the deadlines, and a tick would stop meaning what
#: it says. A coarser look at the motion is a real axis to train
#: along, so this refuses rather than silently drifting.
SLOWEST_FRAME_HZ = 10.0

#: Below this, a stray run of matching bytes is not a verdict. A real
#: ring paints on the order of a thousand pixels at the smallest window
#: the program allows, so the floor is nowhere near anything real.
FEWEST_VERDICT_PIXELS = 200


def _verdict_pixels(rgba: bytes, good: Tuple[int, int, int],
                    bad: Tuple[int, int, int]) -> Tuple[int, int]:
    """How many pixels of the frame are each verdict colour.

    An exact four-byte match rather than a tolerance band, which lets
    the whole frame be counted at C speed instead of a python loop over
    two million pixels. The ring is a flat fill, so its interior really
    is the exact colour — measured at 1794 pixels in an 800x600 window
    and 6777 at 1280x800, with nothing else on screen matching either.

    ``count`` looks at every byte offset rather than every pixel, so a
    run straddling a pixel boundary could in principle be counted. It
    would take the exact three bytes plus an opaque alpha in that
    order, it would add to a tally already in the thousands, and it
    cannot move a tally that is zero far enough to change the verdict.
    """
    return (rgba.count(bytes(good) + b'\xff'),
            rgba.count(bytes(bad) + b'\xff'))


def derive_sight_outcome(rgba: bytes, width: int, height: int,
                         evidence_digests: Any, receipt_id: Optional[int],
                         frame_seq: Optional[int] = None,
                         timestamp_ns: Optional[int] = None
                         ) -> Optional[Dict[str, Any]]:
    """The scalar for one question, read off the ring's colour.

    A resolved ring is painted one of two colours and nothing else on
    screen is either of them, so the count separates cleanly: ``+1.0``
    when the answer was right, ``-1.0`` when it was wrong or never
    came. A frame with no resolved ring yields ``None``, which is not
    the same as zero — it means there is nothing to answer for yet.

    The payload carries no pixel counts. Those would say how big the
    ring was, and through that how large the window is and where the
    dot was; the scalar says only what the learner is owed.
    """
    del width, height                  # the whole frame is searched
    from neural_workshop.ui.tracking import CAUGHT, MISSED
    if not rgba:
        return None
    n_good, n_bad = _verdict_pixels(rgba, CAUGHT, MISSED)
    if max(n_good, n_bad) < FEWEST_VERDICT_PIXELS:
        return None
    scalar = 1.0 if n_good > n_bad else -1.0
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


def verify_sight_outcome(outcome: Optional[Mapping[str, Any]], rgba: bytes,
                         width: int, height: int,
                         archive: Optional[Mapping[str, bytes]] = None,
                         receipt_ledger: Optional[Mapping[int, Any]] = None
                         ) -> bool:
    """The learner-facing verifier for this task's outcomes.

    Every rule the n-back verifier applies applies here too — fail
    closed without both the archive and the ledger, the receipt bound
    to this question's evidence — and only how the scalar is read off
    the frame differs.
    """
    from .outcome import verify_public_outcome
    return verify_public_outcome(outcome, rgba, width, height, archive,
                                 receipt_ledger, derive=derive_sight_outcome)


class OutOfSightEnv:
    """Deterministic, stepped view of one Out of Sight run.

    Constructor arguments own the dials, so a learner never reaches
    into ``cfg``; they survive :meth:`reset`. Everything they set is
    also settable from the task's own options screen, and setting it
    here leaves that screen alone.
    """

    def __init__(self, seed: Optional[int] = None,
                 shm_name: Optional[str] = None,
                 dots: Optional[int] = None,
                 targets: Optional[int] = None,
                 speed: Optional[int] = None,
                 blinds: Optional[int] = None,
                 blind_width: Optional[int] = None,
                 cross_ms: Optional[int] = None,
                 probes: Optional[int] = None,
                 rounds: Optional[int] = None,
                 adaptive: bool = False,
                 frame_hz: float = DEFAULT_FRAME_HZ,
                 visible: bool = False) -> None:
        self._asked = {
            'SIGHT_DOTS': dots, 'SIGHT_TARGETS': targets,
            'SIGHT_SPEED': speed, 'SIGHT_BLINDS': blinds,
            'SIGHT_BLIND_WIDTH': blind_width, 'SIGHT_CROSS_MS': cross_ms,
            'SIGHT_PROBES': probes, 'SIGHT_ROUNDS': rounds,
        }
        self._adaptive = bool(adaptive)
        self._visible = bool(visible)
        self._hz = float(frame_hz)
        if self._hz < SLOWEST_FRAME_HZ:
            raise ValueError('frame_hz must be at least %g'
                             % SLOWEST_FRAME_HZ)
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

        # Question state.
        self._question_digests: List[str] = []
        self._receipt: Optional[Dict[str, Any]] = None
        self._response_open = False
        self._receipt_seq = 0
        self._action_finalized = False
        self._receipt_ledger: Dict[int, Dict[str, Any]] = {}
        self._archive: Dict[str, bytes] = {}
        self._events: List[Dict[str, Any]] = []
        self._delivered: Set[Any] = set()
        self._cached_outcome: Optional[Dict[str, Any]] = None

        self._closed = False
        self.reset(0 if seed is None else seed)

    # --- public API -------------------------------------------------------

    @property
    def n_actions(self) -> int:
        """How many opaque action ports this task offers."""
        return 2

    def reset(self, seed: int = 0) -> Dict[str, Any]:
        """Start a fresh run under *seed* and return the first frame."""
        from neural_workshop import display, state
        from neural_workshop.ui.outofsight import OutOfSight

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

        task = OutOfSight()
        # Nothing may advance behind the driver's back, and no deadline
        # in the task may be read off a clock the driver does not own.
        pyglet.clock.unschedule(task.update)
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
        """Finalize this question's answer. At most one per question.

        *logp* is an optional policy log-propensity stored on the
        receipt so a runtime can map it back to this question; it is
        not interpreted here. Returns a receipt, or a rejection when
        no ring is up or an answer was already given.
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
            # The two ports are the two answers, so pressing both is
            # not an answer and neither is pressing none.
            return rejected

        self.task.answer(bool(indices[0]))
        self._action_finalized = True

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

        was_open = self.task.probe is not None
        self._virtual_now += self._dt
        self.task.update(self._dt)
        self._publish()

        now_open = self.task.probe is not None
        if was_open and not now_open:
            self._response_open = False
        if now_open and not was_open:
            self._question_digests = [self._digest]
            self._open_question()
            self.accounting.logical_trials += 1
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
        turning the task's own dials up must not quietly change what
        a run under a given seed means, so the fallback is the value
        in the source, and the only other way in is this constructor.
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
        task.dot_count = self._dial('SIGHT_DOTS')
        task.start_targets = self._dial('SIGHT_TARGETS')
        task.speed = self._dial('SIGHT_SPEED') / 100.
        task.blind_count = self._dial('SIGHT_BLINDS')
        task.blind_width = self._dial('SIGHT_BLIND_WIDTH') / 100.
        task.cross_gap = self._dial('SIGHT_CROSS_MS') / 1000.
        task.probes_per_round = self._dial('SIGHT_PROBES')
        task.total_rounds = self._dial('SIGHT_ROUNDS')
        # Off by default: a curriculum that moves under the learner is
        # the runtime's business, not the task's.
        task.adaptive = self._adaptive
        task.held = task.clamped_targets(task.start_targets)

    def _clear_run_state(self) -> None:
        self.accounting.reset()
        self._events = []
        self._question_digests = []
        self._receipt = None
        self._response_open = False
        self._receipt_seq = 0
        self._pending = False
        self._consumed = True
        self._archive = {}
        self._action_finalized = False
        self._delivered = set()
        self._cached_outcome = None
        self._receipt_ledger = {}
        self._seq = 0
        self._done = False

    # --- questions --------------------------------------------------------

    def _open_question(self) -> None:
        """Open the action window and pre-register its receipt."""
        self._response_open = True
        self._action_finalized = False
        self._receipt_seq += 1
        stamp = now_ns()
        self._receipt = {
            'ok': True,
            'receipt_id': self._receipt_seq,
            'trial_seq': self._receipt_seq,
            'frame_seq': self._seq,
            'timestamp_ns': stamp,
            'ports': (),
            'logp': None,
            'stimulus_digest': self._digest,
            'window_open_ns': stamp,
        }
        self._receipt_ledger[self._receipt_seq] = dict(self._receipt)

    def _decode_ports(self, ports: Ports) -> List[int]:
        """Normalise an action to a list of valid integer port indices."""
        n = self.n_actions
        if ports is None:
            return []
        if isinstance(ports, int):
            return [ports] if 0 <= ports < n else []
        if isinstance(ports, dict):
            # Semantic names are refused; only integer keys are ports.
            return [k for k, v in ports.items()
                    if v and isinstance(k, int) and 0 <= k < n]
        return [p for p in ports if isinstance(p, int) and 0 <= p < n]

    def _bind_receipt_to_question(self, receipt_id: Optional[int]) -> None:
        """Record which frames the question's receipt answers for."""
        if receipt_id is None or receipt_id not in self._receipt_ledger:
            return
        bound = self._receipt_ledger[receipt_id]
        bound['evidence_digests'] = list(self._question_digests)
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
        """Derive and emit the public outcome for a resolved question."""
        receipt_id = (self._receipt or {}).get('receipt_id')
        key = ('outcome', receipt_id)
        if key in self._delivered:
            return
        self._bind_receipt_to_question(receipt_id)
        outcome = derive_sight_outcome(
            self._rgba, self._width, self._height, self._question_digests,
            receipt_id, frame_seq=self._seq,
            timestamp_ns=self._timestamp_ns)
        if outcome is None:
            return                     # the ring has not resolved yet
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

        if self._response_open or self.task.probe is not None:
            self._question_digests.append(self._digest)
        if self.task.verdict is not None:
            self._publish_outcome()
        if self.task.phase == 'done' and not self._done:
            self._done = True
            self._emit_once(('run_end',), {
                'type': 'run_end',
                'frame_seq': self._seq,
                'timestamp_ns': self._timestamp_ns,
            })


def make_sight_env(seed: int = 0,
                   shm_name: Optional[str] = None) -> OutOfSightEnv:
    """A production environment: the task's own defaults, no adaptation."""
    return OutOfSightEnv(seed=seed, shm_name=shm_name)


__all__ = ['OutOfSightEnv', 'derive_sight_outcome', 'make_sight_env',
           'verify_sight_outcome']
