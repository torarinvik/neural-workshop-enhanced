# -*- coding: utf-8 -*-
"""The stepped agent boundary for Free Kick.

Nine ports: 0-7 turn the aim left and right, raise and lower it, curl
it left and right, and kick harder and softer, each for the step; 8
kicks. Green means the ball crossed the line inside the lit ring.

Clocked: the time to kick runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FreeKickEnv(TaskEnv):
    """Deterministic, stepped view of one Free Kick run."""

    task_class = ('neural_workshop.ui.freekick', 'FreeKick')
    ports = 9
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_free_kick_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> FreeKickEnv:
    """A production environment: the task's own defaults."""
    return FreeKickEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_free_kick_outcome = FreeKickEnv.verifier()

__all__ = ['FreeKickEnv', 'make_free_kick_env',
           'verify_free_kick_outcome']
