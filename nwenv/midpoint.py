# -*- coding: utf-8 -*-
"""The stepped agent boundary for Midpoint.

Five ports: port k picks mark k, counted along the line.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class MidpointEnv(TaskEnv):
    """Deterministic, stepped view of one Midpoint run."""

    task_class = ('neural_workshop.ui.midpoint', 'Midpoint')
    ports = 5
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_midpoint_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> MidpointEnv:
    """A production environment: the task's own defaults."""
    return MidpointEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_midpoint_outcome = MidpointEnv.verifier()

__all__ = ['MidpointEnv', 'make_midpoint_env',
           'verify_midpoint_outcome']
