# -*- coding: utf-8 -*-
"""The stepped agent boundary for Crossings.

Seven ports: 0-6 answer that many crossings. Green means the count was
right.

Turn-based, so it takes the think clock: the lines stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CrossingsEnv(TaskEnv):
    """Deterministic, stepped view of one Crossings run."""

    task_class = ('neural_workshop.ui.crossings', 'Crossings')
    ports = 7
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_crossings_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> CrossingsEnv:
    """A production environment: the task's own defaults."""
    return CrossingsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_crossings_outcome = CrossingsEnv.verifier()

__all__ = ['CrossingsEnv', 'make_crossings_env',
           'verify_crossings_outcome']
