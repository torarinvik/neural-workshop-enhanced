# -*- coding: utf-8 -*-
"""The stepped agent boundary for 3D Matrix.

Up to eight ports: port k picks answer k + 1. Four answers on the
low rungs, six from rung 7, eight from rung 16. Green means the
construction that completes the matrix was picked.

Turn-based, so it takes the think clock: the matrix stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class Matrix3DEnv(TaskEnv):
    """Deterministic, stepped view of one 3D Matrix run."""

    task_class = ('neural_workshop.ui.matrix3d', 'Matrix3D')
    ports = 8
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_matrix_3d_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> Matrix3DEnv:
    """A production environment: the task's own defaults."""
    return Matrix3DEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_matrix_3d_outcome = Matrix3DEnv.verifier()

__all__ = ['Matrix3DEnv', 'make_matrix_3d_env',
           'verify_matrix_3d_outcome']
