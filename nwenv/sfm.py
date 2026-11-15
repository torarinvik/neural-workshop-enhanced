# -*- coding: utf-8 -*-
"""The stepped agent boundary for Shape from Motion.

Six ports, one per answer; a port past the answers the trial offers does
nothing. Green means the answer was right; there is no par.

Clocked: a single frame is a flat spray of dots, and the solid -- or the
way it turns -- is only in how they move.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ShapeFromMotionEnv(TaskEnv):
    """Deterministic, stepped view of one Shape from Motion run."""

    task_class = ('neural_workshop.ui.sfm', 'ShapeFromMotion')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_shape_from_motion_env(seed: int = 0, shm_name: Optional[str] = None
                               ) -> ShapeFromMotionEnv:
    """A production environment: the task's own defaults."""
    return ShapeFromMotionEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_shape_from_motion_outcome = ShapeFromMotionEnv.verifier()

__all__ = ['ShapeFromMotionEnv', 'make_shape_from_motion_env',
           'verify_shape_from_motion_outcome']
