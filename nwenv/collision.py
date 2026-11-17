# -*- coding: utf-8 -*-
"""The stepped agent boundary for Collision Course.

Two ports: 0 says they will hit, 1 that they will miss.

Clocked: the scene plays and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CollisionEnv(TaskEnv):
    """Deterministic, stepped view of one Collision Course run."""

    task_class = ('neural_workshop.ui.collision', 'Collision')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_collision_course_env(seed: int = 0,
                                shm_name: Optional[str] = None) -> CollisionEnv:
    """A production environment: the task's own defaults."""
    return CollisionEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_collision_course_outcome = CollisionEnv.verifier()

__all__ = ['CollisionEnv', 'make_collision_course_env',
           'verify_collision_course_outcome']
