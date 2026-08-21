# -*- coding: utf-8 -*-
"""The shared agent boundary, so a new task is a small file and not a large one.

Three tasks were wrapped before this existed and they came out 628, 680 and
719 lines. Measured across the three, sixteen methods share a name; once the
task's own nouns are stripped, six are byte-identical, one is a near copy and
six more are the same skeleton around a different hook. Only ``__init__``,
``reset`` and ``_apply_dials`` genuinely differ. A fourth task written the
same way would be another six hundred lines of which most is already written.

What this class is careful about is *which* parts a task may change.

A subclass here is not free to override anything it likes. The receipt
ledger, the one-outcome-per-receipt rule, the observation dictionary and the
construction of the verifier are **sealed**: a subclass that overrode
``_emit_once`` could pay one action twice, and one that overrode
``_observation`` could hand the learner a coordinate. Neither would fail
loudly. Every claim this programme makes rests on those staying true, so
:meth:`__init_subclass__` refuses to define a class that touches them, and
the refusal is a test rather than a convention.

What a task actually supplies is small:

``ports``      how many opaque actions there are
``build``      construct the underlying UI task for a seed
``drive``      turn one port index into one action on that task

and, if the defaults do not suit, ``begin``, ``settled``, ``dials`` and
``derive``.

``derive`` has a default that reads the standard verdict label, so a task
that paints :class:`neural_workshop.ui.verdict.VerdictLabel` when a trial
resolves supplies **neither a deriver nor a verifier**. That is the whole of
the hundred-odd lines each existing wrapper spends on the two of them.

The verifier is **generated from** ``derive`` rather than written beside it.
In the hand-written wrappers each task carries a 38-42 line verifier whose
whole job is to re-derive from the archived frame, maintained in parallel
with a 46-59 line deriver. Two functions that must agree, edited separately,
failing open when they drift: a verifier that silently blesses outcomes its
deriver no longer produces is exactly the hole the public-outcome contract
exists to close. Generating one from the other makes them the same function
by construction.

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

#: Methods a task may never redefine. Each one is load-bearing for a claim
#: the programme makes about its own results, and each would fail silently
#: rather than loudly if a subclass weakened it.
SEALED = frozenset({
    '_emit_once',        # one outcome per receipt; two would pay an action twice
    '_observation',      # the learner sees pixels and scalars, nothing else
    '_bind_receipt',     # what frames a receipt answers for
    '_publish_outcome',  # derive -> authenticate -> emit, in that order
    'verifier',          # must be generated from derive, never written beside it
    'observe',
    'step',
})


class SealedContractError(TypeError):
    """A subclass tried to redefine part of the agent boundary."""


class TaskEnv:
    """Base for a stepped, pixel-only agent boundary over one Workshop task."""

    #: Required. How many opaque ports the learner may press.
    ports: int = 0

    # --- the declared form ------------------------------------------------
    #
    # Five wrappers were written against the hooks below before these
    # existed, and they came out 100 to 115 lines each. Set side by side
    # the five differ in about a dozen values and in nothing else: where
    # the task class lives, what one port calls, which phase takes input,
    # which phase means the trial is over, and what the difficulty knobs
    # are called. Everything around those values was the same code five
    # times, including the one part of it that is easy to get wrong --
    # the one-frame wait before dealing the next trial, without which
    # the verdict is cleared on the frame it went up and the outcome is
    # never derivable.
    #
    # So a task may declare the values instead of writing the code. The
    # hooks are all still there and still win when overridden; declaring
    # is the short road, not the only one.

    #: Where the UI task lives: ``('neural_workshop.ui.maze', 'MazeTask')``.
    #: Imported lazily, inside :meth:`build`, because importing a UI module
    #: at boundary-import time pulls in pyglet's window before the headless
    #: options in :mod:`nwenv` have been set.
    task_class: Tuple[str, str] = ('', '')

    #: The task method one port calls. ``'answer'`` means ``task.answer(port)``.
    action: str = ''

    #: Optional per-port arguments, when a port is not just its own index --
    #: ``((0, -1), (0, 1), (-1, 0), (1, 0))`` for a task driven by deltas.
    #: The tuple's length is what :attr:`ports` should be.
    action_table: Tuple[Any, ...] = ()

    #: The phases in which a port does anything. Empty means always open.
    open_phase: Tuple[str, ...] = ()

    #: The phases that mean this trial is over and the next one is owed.
    #: The driver waits one published frame in them before dealing, so the
    #: verdict is on screen for a frame the learner is actually handed.
    settled_phase: Tuple[str, ...] = ()

    #: What deals the next trial once a settled phase has been shown.
    deal: str = '_next_trial'

    #: What starts a run. Most tasks in the workshop count their trials
    #: and call this ``start_run``; the two that run until they are
    #: closed have no run to start and name their round-dealer here
    #: instead. A task with no such method opens in whatever phase it
    #: constructs itself in, which for every task here is a waiting one
    #: -- so getting this wrong is a run that never begins rather than
    #: one that begins wrongly.
    start: str = 'start_run'

    #: Constructor keyword -> attribute on the task. ``RavensEnv(rung=4)``
    #: with ``{'rung': 'start_level'}`` sets ``task.start_level = 4``. A
    #: knob left unset is left alone, so the task keeps its own default.
    knobs: Mapping[str, str] = {}

    #: Task attributes the boundary sets whatever the player's own
    #: preferences say, because a run without them is not derivable.
    #:
    #: Nearly all of these are one setting: several tasks let a player
    #: turn feedback off to go faster, and a trial that resolves with no
    #: verdict painted resolves into nothing a third party could read.
    #: Turning it off is a fine choice for a person, who knows how they
    #: did; it is not available to a learner whose whole payment is that
    #: label. Kept separate from :attr:`knobs` on purpose — a knob is a
    #: difficulty the caller chose, this is a precondition the caller
    #: does not get a say in.
    requires: Mapping[str, Any] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        broken = sorted(SEALED & set(cls.__dict__))
        if broken:
            raise SealedContractError(
                f"{cls.__name__} redefines sealed boundary "
                f"{broken}. These hold the public-outcome contract: a task "
                f"that changes them can pay one action twice or show the "
                f"learner something no verifier can check. Put the "
                f"task-specific part in derive/drive/begin/settled instead."
            )

    # --- required hooks ---------------------------------------------------

    def build(self, seed: int, **dials: Any) -> Any:
        """Construct the underlying UI task.

        The default builds :attr:`task_class`. A task whose constructor
        needs arguments overrides this instead.
        """
        module_name, class_name = self.task_class
        if not class_name:
            raise NotImplementedError(
                '%s declares neither task_class nor build()'
                % type(self).__name__)
        import importlib
        return getattr(importlib.import_module(module_name), class_name)()

    def drive(self, task: Any, port: int) -> None:
        """Apply one opaque port index to the task.

        The default calls :attr:`action` with the port index, or with the
        :attr:`action_table` entry for it when the task wants something
        other than an index. A port past the end of the table does
        nothing, which is not a special case: a task whose rung offers
        four choices out of a possible eight already refuses the other
        four, and the learner has the same amount to discover about a
        port that is out of range this round as about one that is in it.
        """
        if not self.action:
            raise NotImplementedError(
                '%s declares neither action nor drive()'
                % type(self).__name__)
        method = getattr(task, self.action)
        if not self.action_table:
            method(port)
        elif port < len(self.action_table):
            arg = self.action_table[port]
            method(*arg) if isinstance(arg, tuple) else method(arg)

    @staticmethod
    def derive(rgba: bytes, width: int, height: int, evidence: Any,
               receipt_id: Optional[int], frame_seq: Optional[int] = None,
               timestamp_ns: Optional[int] = None,
               neutral: bool = False) -> Optional[Dict[str, Any]]:
        """Read the public scalar off the pixels, or None if unresolved.

        **The default reads the standard verdict label**, so a task that
        paints :class:`neural_workshop.ui.verdict.VerdictLabel` when a trial
        resolves needs no deriver of its own and no verifier either -- both
        already exist, are natively accelerated, and are the same ones every
        other task uses. There is then one pixel reader in the programme to
        get right rather than one per task.

        Override this only for art that cannot carry the standard label.
        The three wrappers written before it existed each do -- fog counts
        world colours, ladder counts tile colours, sight counts ring colours
        -- at a cost of roughly a hundred lines apiece.

        Whatever replaces it must depend on nothing but the frame. A deriver
        that consulted the task's own state would produce outcomes no third
        party can check, which is the whole point of deriving from pixels.
        """
        from .outcome import derive_public_outcome

        if neutral:
            # A conceded trial claims nothing, so it needs no pixels to
            # support it -- but it still has to carry the receipt and the
            # evidence it is conceding against.
            outcome: Dict[str, Any] = {
                'scalar': 0.0,
                'evidence_digests': list(evidence),
                'receipt_id': receipt_id,
            }
            if frame_seq is not None:
                outcome['frame_seq'] = frame_seq
            if timestamp_ns is not None:
                outcome['timestamp_ns'] = timestamp_ns
            return outcome
        return derive_public_outcome(rgba, width, height, evidence,
                                     receipt_id, frame_seq=frame_seq,
                                     timestamp_ns=timestamp_ns)

    # --- optional hooks ---------------------------------------------------

    def begin(self, task: Any) -> None:
        """Open a trial. The default is a task that is always open."""

    def settled(self, task: Any) -> bool:
        """Whether the outcome is readable yet. Default: on every tick."""
        return True

    def dials(self) -> Dict[str, Any]:
        """Difficulty knobs, as the task's own option names."""
        return dict(self._knobs)

    def apply_dials(self, task: Any) -> None:
        """Push this run's knobs into the task that was just built.

        Coerced to the type the task already holds, so ``rung='4'`` off a
        command line sets an int rather than leaving a string somewhere
        that will be compared against numbers three phases later.
        """
        for attr, value in self.requires.items():
            setattr(task, attr, value)
        for name, value in self._knobs.items():
            if value is None:
                continue                      # unset: keep the task's own
            attr = self.knobs[name]
            held = getattr(task, attr, None)
            if isinstance(held, bool):
                value = bool(value)
            elif isinstance(held, int):
                value = int(value)
            elif isinstance(held, float):
                value = float(value)
            setattr(task, attr, value)

    def tick(self, task: Any, dt: float) -> None:
        """Advance the task by *dt*. Clocked tasks update; turn-based do not.

        A task like Out of Sight is a continuous animation and moves whether
        or not anyone acts, so one step is one tick of its clock. A task like
        You Are Here only changes when a key is pressed, and ticking it would
        be a no-op with a cost. :attr:`clocked` says which this is.
        """
        if self.clocked:
            task.update(dt)
        self._deal_when_settled(task)

    def _deal_when_settled(self, task: Any) -> None:
        """Deal the next trial, one published frame after this one settles.

        The wait is the whole of it, and it is the part every wrapper
        written by hand got wrong first. Dealing clears the verdict, so
        going straight there takes the label down on the very frame it
        went up: the driver publishes the next trial's frame, the
        deriver finds nothing on it, and the trial that was scored is
        paid nothing. One frame is published with the label showing
        first, and only then does the next trial open.

        A task that declares no :attr:`settled_phase` is one that deals
        itself -- on its own clock, or because a verdict is not a phase
        it stops in -- and this does nothing to it.
        """
        if not self.settled_phase:
            return
        if getattr(task, 'phase', None) not in self.settled_phase:
            self._settled_seen = False
            return
        if self._settled_seen:
            self._settled_seen = False
            getattr(task, self.deal)()
        else:
            self._settled_seen = True

    def trial_open(self, task: Any) -> bool:
        """Whether an action may be finalized right now.

        The default is :attr:`open_phase`, or -- for a task that declares
        none -- always. A task with distinct question windows names the
        phases they happen in, and the driver opens a receipt as each one
        comes up.
        """
        if not self.open_phase:
            return True
        return getattr(task, 'phase', None) in self.open_phase

    def resolved(self, task: Any) -> bool:
        """Whether the current trial has produced a verdict to pay.

        The default reads the standard verdict label straight off the frame,
        which is the same signal :meth:`derive` reads, so a task painting
        ``VerdictLabel`` answers this without being asked.
        """
        return self.derive(self._rgba, self._width, self._height,
                           [self._digest], None) is not None

    def finished(self, task: Any) -> bool:
        """Whether the whole run is over."""
        return getattr(task, 'phase', None) == 'done'

    # --- sealed boundary --------------------------------------------------

    def _emit_once(self, key: Any, event: Dict[str, Any]) -> bool:
        """Queue *event* unless something with this key already went out."""
        if key in self._delivered:
            return False
        self._delivered.add(key)
        self._events.append(event)
        return True

    def _observation(self) -> Dict[str, Any]:
        """Exactly what the learner may see: pixels, timing, and a scalar."""
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

    def _bind_receipt(self, receipt_id: Optional[int]) -> None:
        """Record which frames this receipt answers for."""
        if receipt_id is None or receipt_id not in self._receipt_ledger:
            return
        bound = self._receipt_ledger[receipt_id]
        evidence = list(self._trial_digests)
        bound['evidence_digests'] = evidence
        if evidence:
            # A window opens on whatever frame is up, but what it is
            # answerable against is the trial. Without this the two disagree
            # and every outcome fails to verify.
            bound['stimulus_digest'] = evidence[0]
        bound['feedback_digest'] = self._digest
        bound['feedback_frame_seq'] = self._seq

    def _publish_outcome(self, neutral: bool = False) -> None:
        """Derive, authenticate and emit the public outcome for a trial."""
        receipt_id = (self._receipt or {}).get('receipt_id')
        key = ('outcome', receipt_id)
        if key in self._delivered:
            return
        if not self._trial_digests:
            self._trial_digests = [self._digest]
        self._bind_receipt(receipt_id)
        outcome = type(self).derive(
            self._rgba, self._width, self._height, self._trial_digests,
            receipt_id, frame_seq=self._seq,
            timestamp_ns=self._timestamp_ns, neutral=neutral)
        if outcome is None:
            return                      # the trial has not resolved yet
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

    @classmethod
    def verifier(cls):
        """Build this task's learner-facing verifier out of its deriver.

        A claim of zero is allowed on any frame, because claiming zero never
        claims more than was earned. Everything worth something keeps the
        strict reading and still has to be visible in the pixels, which is
        the only direction a verifier has to police.
        """
        from .outcome import verify_public_outcome

        def verify(outcome: Optional[Mapping[str, Any]], rgba: bytes,
                   width: int, height: int,
                   archive: Optional[Mapping[str, bytes]] = None,
                   receipt_ledger: Optional[Mapping[int, Any]] = None) -> bool:
            conceded = float((outcome or {}).get('scalar', 0.0)) == 0.0

            def derive(frame, w, h, evidence, receipt_id, frame_seq=None,
                       timestamp_ns=None):
                return cls.derive(frame, w, h, evidence, receipt_id,
                                  frame_seq=frame_seq,
                                  timestamp_ns=timestamp_ns,
                                  neutral=conceded)

            return verify_public_outcome(outcome, rgba, width, height,
                                         archive, receipt_ledger,
                                         derive=derive)

        verify.__name__ = f'verify_{cls.__name__}_outcome'
        verify.__doc__ = (
            f'Verifier for {cls.__name__}, generated from its deriver so the '
            f'two cannot drift apart.'
        )
        return verify

    def observe(self) -> Dict[str, Any]:
        self._consumed = True
        return self._observation()

    def step(self, ports: Ports = None) -> Tuple[Dict[str, Any],
                                                 List[Dict[str, Any]], bool]:
        self.act(ports)
        feedback = self.advance()
        events = list(self._events)
        self._events.clear()
        return feedback, events, bool(self._done)

    @property
    def n_actions(self) -> int:
        return self._runtime_ports or int(self.ports)

    # --- the driving loop -------------------------------------------------

    #: Whether the task advances on its own clock. See :meth:`tick`.
    clocked: bool = True
    #: Pay a fresh verdict once per *action* instead of once per trial.
    #: For tasks that paint a consequence verdict after every move (dense
    #: shaping).  Payment stays tied to the action's receipt through the
    #: owed-outcome path, so a verdict lingering across ticks still cannot
    #: multiply: with no action finalized, nothing is owed and nothing pays.
    #: Only the neutral-outcomes accounting honours this; the sparse path
    #: keeps its per-trial dedupe.
    dense: bool = False

    #: The slowest a clocked task may be driven. Below this a task's own
    #: motion clamps start to bite and a tick stops meaning what it says.
    slowest_frame_hz: float = 10.0

    @property
    def paying_densely(self) -> bool:
        """Whether a per-action verdict would actually be paid per action.

        :attr:`dense` is honoured only by the neutral-outcomes
        accounting, so a task that paints a consequence after every
        move must ask this before switching that painting on. Built the
        plain way, the first such label is on screen the moment the
        driver next looks, and the sparse path pays it as *the trial's*
        verdict — the trial then scores "that move got warmer" instead
        of "the run was won", and a run of random actions comes out
        looking like a run of skilled ones.

        Measured on Chain of Custody before this existed: random play
        scored 44% against a guessing floor of 38%, all of it earned by
        claw moves that happened to close a distance. On You Are Here
        it paid a single +1 on a maze that random play had not solved
        and could not have.
        """
        return bool(self.dense and self._neutral_outcomes)

    def __init__(self, seed: Optional[int] = None,
                 shm_name: Optional[str] = None,
                 neutral_outcomes: bool = False,
                 runtime_ports: int = 0,
                 frame_hz: float = 60.0,
                 visible: bool = False,
                 autostart: bool = True,
                 **dials: Any) -> None:
        # A window on every tick and a verdict for every action, the ones
        # outside a trial worth nothing. A runtime acting on a fixed clock
        # needs both; a caller reading the task's own contract wants neither.
        self._neutral_outcomes = bool(neutral_outcomes)
        # A runtime built around a wider decoder can be given the width it
        # expects: the extra ports do nothing, and which ones those are is
        # not said here -- the learner has as much to discover about them as
        # about the ones that act.
        self._runtime_ports = int(runtime_ports)
        if self._runtime_ports and self._runtime_ports < int(self.ports):
            raise ValueError('a runtime needs at least the task\'s own ports')
        self._visible = bool(visible)
        self._hz = float(frame_hz)
        if self.clocked and self._hz < self.slowest_frame_hz:
            raise ValueError('frame_hz must be at least %g'
                             % self.slowest_frame_hz)
        self._dt = 1. / self._hz
        self._asked = dict(dials)
        # A declared knob is a constructor keyword. One that is not
        # declared is refused rather than ignored: a run started with
        # `rungs=7` where the task spells it `rung` would otherwise open
        # at the default difficulty and say nothing about it, and every
        # number that came out of it would be about the wrong ladder.
        stray = sorted(set(dials) - set(self.knobs))
        if stray and self.knobs:
            raise TypeError('%s has no knob %s; it has %s'
                            % (type(self).__name__, ', '.join(stray),
                               ', '.join(sorted(self.knobs)) or 'none'))
        self._knobs = {name: dials.get(name) for name in self.knobs}

        self._export = FrameExport(
            shm_name=shm_name or os.environ.get('NW_SHM'))
        self.accounting = Accounting()
        self.task: Any = None
        self._virtual_now = 0.0
        self._closed = False
        self._blank_state()
        if autostart:
            self.reset(0 if seed is None else seed)

    def _blank_state(self) -> None:
        self._seq = 0
        self._timestamp_ns = 0
        self._width = 0
        self._height = 0
        self._rgba = b''
        self._digest = ''
        self._pending = False
        self._consumed = True
        self._done = False
        self._trial_digests: List[str] = []
        self._receipt: Optional[Dict[str, Any]] = None
        self._response_open = False
        self._receipt_seq = 0
        self._action_finalized = False
        self._outcome_owed = False
        self._trial_seq = 0
        self._scored_trial = -1
        self._receipt_ledger: Dict[int, Dict[str, Any]] = {}
        self._archive: Dict[str, bytes] = {}
        self._events: List[Dict[str, Any]] = []
        self._delivered: Set[Any] = set()
        self._cached_outcome: Optional[Dict[str, Any]] = None
        self._settled_seen = False

    def reset(self, seed: int = 0) -> Dict[str, Any]:
        """Start a fresh run under *seed* and return the first frame."""
        from neural_workshop import display, state

        seed = int(seed)
        random.seed(seed)
        if self.task is not None:
            try:
                self.task.close()
            except Exception:
                pass
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

        task = self.build(seed)
        # Nothing may advance behind the driver's back, and no deadline in
        # the task may be read off a clock the driver does not own.
        if hasattr(task, 'update'):
            pyglet.clock.unschedule(task.update)
        self._virtual_now = 0.0
        if hasattr(task, 'clock'):
            task.clock = lambda: self._virtual_now
        if hasattr(task, 'rng'):
            task.rng = random.Random(seed)
        self.apply_dials(task)
        self.task = task

        self.accounting.reset()
        self._blank_state()
        starter = getattr(task, self.start, None)
        if callable(starter):
            starter()
        self._publish()
        if self.trial_open(task):
            self._open_trial()
        return self.observe()

    def act(self, ports: Ports = None,
            logp: Optional[float] = None) -> Dict[str, Any]:
        """Finalize this trial's action. At most one per trial."""
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
            return rejected

        index = int(indices[0])
        if index < int(self.ports):
            self.drive(self.task, index)
        elif not self._neutral_outcomes:
            return rejected           # a port that does nothing is no action
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

        was_open = self.trial_open(self.task)
        self._virtual_now += self._dt
        self.tick(self.task, self._dt)
        self._publish()

        now_open = self.trial_open(self.task)
        if now_open and not was_open:
            self._trial_digests = [self._digest]
            self._trial_seq += 1
            self.accounting.logical_trials += 1
        if was_open and not now_open:
            self._response_open = False
        if now_open and (self._action_finalized or not self._response_open):
            self._open_trial()
        return self.observe()

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

    def _open_trial(self) -> None:
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

        if self._response_open:
            self._trial_digests.append(self._digest)

        settled = self.resolved(self.task)
        if self._neutral_outcomes:
            # A verdict lingers on screen. Paying it on every tick it is up
            # would multiply one answer into many and drown the tally; it is
            # owed once, to the trial it answers.
            fresh = settled and (self.dense
                                 or self._scored_trial != self._trial_seq)
            if self._outcome_owed:
                self._outcome_owed = False
                if fresh:
                    self._scored_trial = self._trial_seq
                self._publish_outcome(neutral=not fresh)
        elif settled and self._scored_trial != self._trial_seq:
            self._scored_trial = self._trial_seq
            self._publish_outcome()

        if self.finished(self.task) and not self._done:
            self._done = True
            self._emit_once(('run_end',), {
                'type': 'run_end',
                'frame_seq': self._seq,
                'timestamp_ns': self._timestamp_ns,
            })
