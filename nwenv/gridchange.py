# -*- coding: utf-8 -*-
"""The stepped agent boundary for Grid Change.

Six ports: port k picks candidate k.

Turn-based, so it takes the think clock: the grids stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class GridChangeEnv(TaskEnv):
    """Deterministic, stepped view of one Grid Change run."""

    task_class = ('neural_workshop.ui.gridchange', 'GridChange')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_grid_change_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> GridChangeEnv:
    """A production environment: the task's own defaults."""
    return GridChangeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_grid_change_outcome = GridChangeEnv.verifier()

__all__ = ['GridChangeEnv', 'make_grid_change_env',
           'verify_grid_change_outcome']
