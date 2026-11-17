# -*- coding: utf-8 -*-
"""The stepped agent boundary for Contour.

Four ports: 0 says left and 1 right; with four parts, port k picks
part k in reading order (top left, top right, bottom left, bottom
right).

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ContourEnv(TaskEnv):
    """Deterministic, stepped view of one Contour run."""

    task_class = ('neural_workshop.ui.contour', 'Contour')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_contour_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> ContourEnv:
    """A production environment: the task's own defaults."""
    return ContourEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_contour_outcome = ContourEnv.verifier()

__all__ = ['ContourEnv', 'make_contour_env',
           'verify_contour_outcome']
