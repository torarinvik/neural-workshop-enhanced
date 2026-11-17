# -*- coding: utf-8 -*-
"""The stepped agent boundary for Far Size.

Four ports: port k picks post k, from the left.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FarSizeEnv(TaskEnv):
    """Deterministic, stepped view of one Far Size run."""

    task_class = ('neural_workshop.ui.farsize', 'FarSize')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_far_size_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> FarSizeEnv:
    """A production environment: the task's own defaults."""
    return FarSizeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_far_size_outcome = FarSizeEnv.verifier()

__all__ = ['FarSizeEnv', 'make_far_size_env',
           'verify_far_size_outcome']
