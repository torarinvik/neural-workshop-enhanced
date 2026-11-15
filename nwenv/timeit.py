# -*- coding: utf-8 -*-
"""The stepped agent boundary for Time It.

One port: 0 presses. Green means the press came while the hidden ball
was at the mark, give or take the window.

Clocked: the ball moves whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TimeItEnv(TaskEnv):
    """Deterministic, stepped view of one Time It run."""

    task_class = ('neural_workshop.ui.timeit', 'TimeIt')
    ports = 1
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_time_it_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> TimeItEnv:
    """A production environment: the task's own defaults."""
    return TimeItEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_time_it_outcome = TimeItEnv.verifier()

__all__ = ['TimeItEnv', 'make_time_it_env',
           'verify_time_it_outcome']
