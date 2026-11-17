# -*- coding: utf-8 -*-
"""The stepped agent boundary for Steeper.

Two ports: 0 says the left line, 1 the right.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SteeperEnv(TaskEnv):
    """Deterministic, stepped view of one Steeper run."""

    task_class = ('neural_workshop.ui.steeper', 'Steeper')
    ports = 2
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_steeper_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> SteeperEnv:
    """A production environment: the task's own defaults."""
    return SteeperEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_steeper_outcome = SteeperEnv.verifier()

__all__ = ['SteeperEnv', 'make_steeper_env',
           'verify_steeper_outcome']
