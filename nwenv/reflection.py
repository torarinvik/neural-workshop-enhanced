# -*- coding: utf-8 -*-
"""The stepped agent boundary for Reflection.

Four ports: port k picks figure k (reading order on the right).

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ReflectionEnv(TaskEnv):
    """Deterministic, stepped view of one Reflection run."""

    task_class = ('neural_workshop.ui.reflection', 'Reflection')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_reflection_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> ReflectionEnv:
    """A production environment: the task's own defaults."""
    return ReflectionEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_reflection_outcome = ReflectionEnv.verifier()

__all__ = ['ReflectionEnv', 'make_reflection_env',
           'verify_reflection_outcome']
