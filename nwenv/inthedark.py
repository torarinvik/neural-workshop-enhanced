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

from typing import Optional

from .taskenv import TaskEnv


class InTheDarkEnv(TaskEnv):
    """Deterministic, stepped view of one In the Dark run.

    Five ports, one to a colour, in an order the learner has to
    discover — and on rungs with fewer colours than that the spare
    ports do nothing, which the task itself refuses rather than the
    boundary guessing at.
    """

    task_class = ('neural_workshop.ui.inthedark', 'InTheDark')
    ports = 5
    clocked = True
    action = 'answer'
    #: Only while a lamp is standing as a question. The walk before it is
    #: watched rather than played.
    open_phase = ('asking',)
    settled_phase = ('scored',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'seconds': 'room_seconds'}


def make_inthedark_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> InTheDarkEnv:
    """A production environment: the task's own defaults."""
    return InTheDarkEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_inthedark_outcome = InTheDarkEnv.verifier()

__all__ = ['InTheDarkEnv', 'make_inthedark_env', 'verify_inthedark_outcome']
