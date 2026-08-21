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
``derive``     read the public scalar off the pixels

and, if the default does not suit, ``begin``, ``settled`` and ``dials``.

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

from typing import (Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple,
                    Union)

from .frames import digest_rgba
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
        """Construct the underlying UI task. Task-specific."""
        raise NotImplementedError

    def drive(self, task: Any, port: int) -> None:
        """Apply one opaque port index to the task. Task-specific."""
        raise NotImplementedError

    @staticmethod
    def derive(rgba: bytes, width: int, height: int, evidence: Any,
               receipt_id: Optional[int], frame_seq: Optional[int] = None,
               timestamp_ns: Optional[int] = None,
               neutral: bool = False) -> Optional[Dict[str, Any]]:
        """Read the public scalar off the pixels, or None if unresolved.

        Must depend on nothing but the frame. A deriver that consulted the
        task's own state would produce outcomes no third party can check,
        which is the whole point of deriving from pixels.
        """
        raise NotImplementedError

    # --- optional hooks ---------------------------------------------------

    def begin(self, task: Any) -> None:
        """Open a trial. The default is a task that is always open."""

    def settled(self, task: Any) -> bool:
        """Whether the outcome is readable yet. Default: on every tick."""
        return True

    def dials(self) -> Dict[str, Any]:
        """Difficulty knobs, as the task's own option names."""
        return {}

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
        return int(self.ports)
