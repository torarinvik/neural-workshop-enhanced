# -*- coding: utf-8 -*-
"""The stepped agent boundary for Syllogisms.

Twenty-seven ports: one an answer. That is the widest answer any
family offers — the twenty-six ways one thing can stand to another in
three dimensions, and standing in the same place — and it is the
task's ceiling rather than any rung's. On rung one three ports are
live and twenty-four are inert; on rung nine every one of them is.

**A port the rung does not offer does nothing**, and leaves the frame
exactly as it was. That is the same honest silence walking into a wall
gets in the Maze, and it is the reason the count can be a ceiling
without the low rungs being a lottery with twenty-four blanks in it.

Green means the answer was the one that follows. There is nothing
partial here to be nearly right about: an answer is an index, and
either it is the one the premises force or it is not.

**Random play is paid here**, and paid mostly red — one port in three
at the bottom of the ladder, one in twenty-seven at rung nine. That is
the same shape Scramble and Algebra have, and what a learner gets for
free is what a wrong answer costs. The green still needs the test in
``tests/test_env_tasks.py`` that answers a known question through
these ports and reads the verdict off the frame.

**Not shaped, and could not honestly be.** There is one action a
trial. The only potential available before it is which answer is
right, which is the answer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from neural_workshop.syllogism import MOST_OPTIONS

from .taskenv import TaskEnv


class SyllogismEnv(TaskEnv):
    """Deterministic, stepped view of one Syllogisms run."""

    task_class = ('neural_workshop.ui.syllogism', 'Syllogism')
    ports = MOST_OPTIONS
    #: Nothing moves on its own; the lines wait as long as they are left.
    clocked = False
    action = 'choose'
    open_phase = ('asking',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'show_working': 'show_working', 'adaptive': 'adaptive'}


def make_syllogism_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> SyllogismEnv:
    """A production environment: the task's own defaults."""
    return SyllogismEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_syllogism_outcome = SyllogismEnv.verifier()

__all__ = ['SyllogismEnv', 'make_syllogism_env', 'verify_syllogism_outcome']
