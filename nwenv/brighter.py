# -*- coding: utf-8 -*-
"""The stepped agent boundary for Brighter.

Four ports: port k picks patch k, from the left.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BrighterEnv(TaskEnv):
    """Deterministic, stepped view of one Brighter run."""

    task_class = ('neural_workshop.ui.brighter', 'Brighter')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_brighter_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> BrighterEnv:
    """A production environment: the task's own defaults."""
    return BrighterEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_brighter_outcome = BrighterEnv.verifier()

__all__ = ['BrighterEnv', 'make_brighter_env',
           'verify_brighter_outcome']
