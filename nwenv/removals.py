# -*- coding: utf-8 -*-
"""The stepped agent boundary for Removals.

The task is two phases and only one of them takes actions. A round plays
its moves out on a clock — thing into box, box into van, two things swapped
— and nothing the learner does while that is happening means anything. Then
the doors close and it is asked which van some of the things ended up in,
one question at a time, and those are the only moments a port does
anything.

So :meth:`trial_open` is the asking phase and nothing else. The frames of
the walk still go by and are still evidence — they are, in fact, the whole
of the evidence, because the answer is not in any single one of them — but
no receipt opens against them.

The task is **clocked**: its moves advance on ``update`` against a clock the
boundary owns, so one step is one tick and the walk goes by at the rung's
own pace whatever the learner does. That is not a cost to be optimised away.
A learner that could skip the walk would be answering a question it had not
been asked.

One round pays one scalar, not one per question. The verdict goes up when
the last answer is in, and it is green only for a clean round: five
questions with four right is not four fifths of an answer, it is a yard the
learner did not have.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .taskenv import TaskEnv


class RemovalsEnv(TaskEnv):
    """Deterministic, stepped view of one Removals run.

    Five ports, one to a van, in an order the learner has to discover —
    and on rungs with fewer vans than that the spare ports do nothing,
    which the task itself already refuses rather than the boundary
    guessing at.
    """

    ports = 5
    clocked = True

    def __init__(self, seed: Optional[int] = None,
                 rung: Optional[int] = None,
                 trials: Optional[int] = None,
                 seconds: Optional[float] = None,
                 **kwargs: Any) -> None:
        self._rung = rung
        self._trials = trials
        self._seconds = seconds
        self._scored_seen = False
        super().__init__(seed=seed, **kwargs)

    def build(self, seed: int, **dials: Any) -> Any:
        from neural_workshop.ui.removals import Removals
        return Removals()

    def apply_dials(self, task: Any) -> None:
        if self._rung is not None:
            task.start_rung = int(self._rung)
        if self._trials is not None:
            task.total_trials = int(self._trials)
        if self._seconds is not None:
            task.move_seconds = float(self._seconds)

    def drive(self, task: Any, port: int) -> None:
        task.answer(port)

    def trial_open(self, task: Any) -> bool:
        """Only while a question is standing.

        The walk before it is watched rather than played, and the
        verdict after it is read rather than answered.
        """
        return getattr(task, 'phase', None) == 'asking'

    def tick(self, task: Any, dt: float) -> None:
        """Advance the walk, and deal the next round once one is scored.

        The wait before dealing is the same one You Are Here needs and
        for the same reason: dealing clears the verdict, so going
        straight there would take the label down on the frame it went up
        and the outcome would never be derivable. One frame is published
        with it showing first.
        """
        task.update(dt)
        if getattr(task, 'phase', None) != 'scored':
            self._scored_seen = False
            return
        if self._scored_seen:
            self._scored_seen = False
            task._next_trial()
        else:
            self._scored_seen = True

    def dials(self) -> Dict[str, Any]:
        return {'rung': self._rung, 'trials': self._trials,
                'seconds': self._seconds}


def make_removals_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> RemovalsEnv:
    """A production environment: the task's own defaults."""
    return RemovalsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_removals_outcome = RemovalsEnv.verifier()

__all__ = ['RemovalsEnv', 'make_removals_env', 'verify_removals_outcome']
