# -*- coding: utf-8 -*-
"""The stepped agent boundary for Delay.

Two ports: port 0 takes the small reward now (or gives up a wait),
port 1 waits for the large one. A trial is one run of a minute (45
seconds from rung 20); green means it collected at least par, from the
best fixed rule on the identical run.

Clocked: waiting is spent in the run's own time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class DelayEnv(TaskEnv):
    """Deterministic, stepped view of one Delay run."""

    task_class = ('neural_workshop.ui.delay', 'Delay')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_delay_env(seed: int = 0,
                   shm_name: Optional[str] = None) -> DelayEnv:
    """A production environment: the task's own defaults."""
    return DelayEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_delay_outcome = DelayEnv.verifier()

__all__ = ['DelayEnv', 'make_delay_env', 'verify_delay_outcome']
