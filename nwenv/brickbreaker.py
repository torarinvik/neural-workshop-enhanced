# -*- coding: utf-8 -*-
"""The stepped agent boundary for 3D Brick Breaker.

Fourteen ports: 0-7 slide the paddle left, right, up, down, up-left,
up-right, down-left and down-right; 8-11 turn its face left, right, up
and down; 12 levels it; 13 changes its colour. Green means every
brick that has to go was broken before the lives or the time ran out.

Clocked: the ball flies whether or not the agent acts -- though the first
ball is not served until the paddle is first touched.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BrickBreakerEnv(TaskEnv):
    """Deterministic, stepped view of one 3D Brick Breaker run."""

    task_class = ('neural_workshop.ui.brickbreaker', 'BrickBreaker')
    ports = 14
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_brick_breaker_3d_env(seed: int = 0,
                                shm_name: Optional[str] = None) -> BrickBreakerEnv:
    """A production environment: the task's own defaults."""
    return BrickBreakerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_brick_breaker_3d_outcome = BrickBreakerEnv.verifier()

__all__ = ['BrickBreakerEnv', 'make_brick_breaker_3d_env',
           'verify_brick_breaker_3d_outcome']
