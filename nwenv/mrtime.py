# -*- coding: utf-8 -*-
"""The stepped agent boundary for Mr. Time.

Fourteen ports: ten digits, a decimal point, a backspace, a submit,
and one more that is simply *now*. The first thirteen compose an
answer the way Count's twelve do; the fourteenth is the produce half,
where the action is not what you say but when you take it.

**This is the one task where the clock is the content.** Every other
wrapped task would play the same if the driver ran twice as fast: the
frames would arrive quicker and the answer would not change. Here the
answer *is* the number of frames, so the virtual clock the driver owns
is not a convenience for stepping — it is the thing being measured.
That has a consequence worth stating plainly rather than discovering:
one step is one frame, a frame is 16.7 ms at the default rate, and
therefore **the finest interval the boundary can express is one frame**.
The top two rungs ask for bands below that and are unreachable through
here at any amount of training. They are unreachable by a person too,
for a different reason, and the task's own docstring says why both.

The floor is honest and it is low. A run of random ports reaches a
verdict on nearly every trial — one port is submit, one port is now,
and a nonsense answer submitted is a nonsense answer marked — so the
boundary pays, and what it pays is almost entirely red. The green
needs the knowing-answer test in ``tests/test_env_tasks.py``, which
reads the interval off the task and answers it through these same
ports. Mr. Time belongs in both places, the way Scramble and Algebra
do.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Ports 0-9 are the digits they look like — but only to a reader of
#: this file. The learner is told nothing about which port is which.
DIGITS = 10
POINT, BACKSPACE, SUBMIT, NOW = 10, 11, 12, 13


class MrTimeEnv(TaskEnv):
    """Deterministic, stepped view of one Mr. Time run."""

    task_class = ('neural_workshop.ui.mrtime', 'MrTime')
    ports = 14
    clocked = True
    open_phase = ('asking', 'counting')
    settled_phase = ('feedback',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'mode': 'mode', 'gap_ms': 'max_gap_ms',
             'flash_ms': 'flash_ms', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Four methods, so this one is not a table.

        A port that belongs to the other half of the task does nothing
        — digits during a produce trial, *now* during a recall one —
        and nothing here says which half is running. That is the
        ceiling rule: the ports are the task's, not the trial's.
        """
        if port < DIGITS:
            task.type_digit(str(port))
        elif port == POINT:
            task.type_point()
        elif port == BACKSPACE:
            task.backspace()
        elif port == SUBMIT:
            task.submit()
        else:
            task.act_now()


def make_mrtime_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> MrTimeEnv:
    """A production environment: the task's own defaults."""
    return MrTimeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_mrtime_outcome = MrTimeEnv.verifier()

__all__ = ['MrTimeEnv', 'make_mrtime_env', 'verify_mrtime_outcome']
