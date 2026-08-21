# -*- coding: utf-8 -*-
"""The stepped agent boundary for Count.

Twelve ports: ten digits, a backspace, and a submit. This is the only
task on the boundary whose answer is *composed* rather than chosen, and
that is deliberate — a wrong digit is not a wrong guess, it is an answer
built out of several actions of which one was wrong, and the learner has
to notice and take it back.

It also means the port that pays is almost never the port that mattered.
Submit is the action that draws the verdict, and by then the answer was
already decided one to three actions earlier. Credit assignment over a
composed answer is the difficulty here, on top of the counting.

Sixty shapes is the top of the ladder, so three digits is the widest an
answer ever gets and the task refuses a fourth.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Ports 0-9 are the digits they look like — but only to a reader of this
#: file. The learner is told nothing about which port is which, and has
#: to find the ordering as well as the count.
DIGITS = 10
BACKSPACE, SUBMIT = 10, 11


class CountingEnv(TaskEnv):
    """Deterministic, stepped view of one Count run."""

    task_class = ('neural_workshop.ui.counting', 'Counting')
    ports = 12
    clocked = True
    open_phase = ('showing', 'hidden')
    settled_phase = ('feedback',)
    knobs = {'rung': 'start_count', 'trials': 'total_trials',
             'kind': 'kind', 'exposure_ms': 'exposure_ms',
             'adaptive': 'adaptive'}
    requires = {'show_answer': True}

    def drive(self, task: Any, port: int) -> None:
        """Three different methods, so this one is not declared.

        Submit on an empty answer does nothing, which is the task's own
        rule rather than the boundary's: there is nothing to score.
        """
        if port < DIGITS:
            task.type_digit(str(port))
        elif port == BACKSPACE:
            task.backspace()
        else:
            task.submit()


def make_counting_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> CountingEnv:
    """A production environment: the task's own defaults."""
    return CountingEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_counting_outcome = CountingEnv.verifier()

__all__ = ['CountingEnv', 'make_counting_env', 'verify_counting_outcome']
