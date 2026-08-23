# -*- coding: utf-8 -*-
"""The stepped agent boundary for Algebra.

Twenty-one ports: nineteen characters, a rub-out and a submit. The
characters are the ten digits, the two letters the task uses, and the
seven signs — which is a typewriter rather than a set of moves, the
same shape Scramble has and for the same reason: the answer is a
string and there is nothing else to steer.

**Most of those ports do nothing on most rungs**, and that is the
declared contract rather than an oversight. ``ports`` is the task's
ceiling, not a rung's. On rung one the answer is a two-digit number
and the bracket ports are inert; on rung eleven it is a polynomial in
two letters and every one of them is live.

Green means the answer is exactly right. There is no tolerance
anywhere in this task: a numeric answer is compared as an exact
:class:`~fractions.Fraction` and a symbolic one by canonical form, so
``64/35`` and ``128/70`` are one answer and ``1.828`` is not an answer
at all. A near miss in arithmetic is a wrong answer, which is the one
thing arithmetic is about.

**Random play is paid here, and paid nothing but red**, because one
port is submit and a submitted string of digits is a submitted
answer — the same shape as Scramble and Donkey. What a learner gets
for free is the cost of a wrong answer. The green needs the test in
``tests/test_env_tasks.py`` that types a known answer through these
ports and still reads the verdict off the frame.

**Not shaped, and could not honestly be.** The only potential
available is how much of the answer has been typed, which is the
answer. Paying per correct character would hand over the sentence a
letter at a time, exactly as it would in Scramble. It pays once.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: The keyboard, in port order. Digits, the two letters a rung may
#: use, then the signs.
KEYS = '0123456789xy+-*/^()'
BACK, SUBMIT = len(KEYS), len(KEYS) + 1


class AlgebraEnv(TaskEnv):
    """Deterministic, stepped view of one Algebra run."""

    task_class = ('neural_workshop.ui.algebra', 'Algebra')
    ports = SUBMIT + 1
    #: Nothing moves on its own; the question waits as long as it is left.
    clocked = False
    open_phase = ('working',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'show_working': 'show_working', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Three methods, so this one is not declared.

        A rub-out with nothing to rub out and a submit with nothing
        typed are both refused by the task and leave the frame
        unchanged — the same honest silence walking into a wall gets
        in the Maze.
        """
        if port < len(KEYS):
            task.write(KEYS[port])
        elif port == BACK:
            task.erase()
        else:
            task.submit()


def make_algebra_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> AlgebraEnv:
    """A production environment: the task's own defaults."""
    return AlgebraEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_algebra_outcome = AlgebraEnv.verifier()

__all__ = ['AlgebraEnv', 'KEYS', 'make_algebra_env', 'verify_algebra_outcome']
