# -*- coding: utf-8 -*-
"""The stepped agent boundary for Gaze.

Eight ports: port k picks thing k+1.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class GazeEnv(TaskEnv):
    """Deterministic, stepped view of one Gaze run."""

    task_class = ('neural_workshop.ui.gaze', 'Gaze')
    ports = 8
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_gaze_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> GazeEnv:
    """A production environment: the task's own defaults."""
    return GazeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_gaze_outcome = GazeEnv.verifier()

__all__ = ['GazeEnv', 'make_gaze_env',
           'verify_gaze_outcome']
