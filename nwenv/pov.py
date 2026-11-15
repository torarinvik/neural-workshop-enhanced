# -*- coding: utf-8 -*-
"""The stepped agent boundary for Point of View.

Five ports, one per picture; a port past the pictures the trial offers
does nothing. Green means the picture chosen is the one the camera on
the map takes; there is no par.

Turn-based, so it takes the think clock: map and pictures stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class PointOfViewEnv(TaskEnv):
    """Deterministic, stepped view of one Point of View run."""

    task_class = ('neural_workshop.ui.pov', 'PointOfView')
    ports = 5
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_point_of_view_env(seed: int = 0, shm_name: Optional[str] = None
                           ) -> PointOfViewEnv:
    """A production environment: the task's own defaults."""
    return PointOfViewEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_point_of_view_outcome = PointOfViewEnv.verifier()

__all__ = ['PointOfViewEnv', 'make_point_of_view_env',
           'verify_point_of_view_outcome']
