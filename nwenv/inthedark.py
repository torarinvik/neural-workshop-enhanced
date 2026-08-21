# -*- coding: utf-8 -*-
"""The stepped agent boundary for In the Dark.

The walk is watched and the questions are played, and only the second of
those takes ports. Rooms go by on a clock the boundary owns — paint a lamp,
turn one on to the next colour, swap two over, copy one onto another — and
nothing the learner does while they do means anything. Then the lights come
up and it is asked what colour some of the lamps ended on, and those are the
only moments a port does anything.

The frames of the walk are still the whole of the evidence, because the
answer is in none of them singly: the lamps are drawn as empty sockets from
first room to last, so two runs with different colours behind them are the
same picture pixel for pixel. No receipt opens against those frames, and a
learner that could skip them would be answering a question it had not been
asked.

One round pays one scalar, green only for a clean one. That is not
squeamishness about partial credit — below the rung's floor a player holds
no information at all and scores exactly one in ``colours``, so four right
out of five is not four fifths of an answer, it is one lamp carried and the
rest guessed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .taskenv import TaskEnv


class InTheDarkEnv(TaskEnv):
    """Deterministic, stepped view of one In the Dark run.

    Five ports, one to a colour, in an order the learner has to
    discover — and on rungs with fewer colours than that the spare
    ports do nothing, which the task itself refuses rather than the
    boundary guessing at.
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
        from neural_workshop.ui.inthedark import InTheDark
        return InTheDark()

    def apply_dials(self, task: Any) -> None:
        if self._rung is not None:
            task.start_rung = int(self._rung)
        if self._trials is not None:
            task.total_trials = int(self._trials)
        if self._seconds is not None:
            task.room_seconds = float(self._seconds)

    def drive(self, task: Any, port: int) -> None:
        task.answer(port)

    def trial_open(self, task: Any) -> bool:
        """Only while a lamp is standing as a question."""
        return getattr(task, 'phase', None) == 'asking'

    def tick(self, task: Any, dt: float) -> None:
        """Advance the walk, and deal the next round once one is scored.

        The wait before dealing is the one every task on this boundary
        needs: dealing clears the verdict, so going straight there
        would take the label down on the frame it went up and the
        outcome would never be derivable.
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


def make_inthedark_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> InTheDarkEnv:
    """A production environment: the task's own defaults."""
    return InTheDarkEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_inthedark_outcome = InTheDarkEnv.verifier()

__all__ = ['InTheDarkEnv', 'make_inthedark_env', 'verify_inthedark_outcome']
