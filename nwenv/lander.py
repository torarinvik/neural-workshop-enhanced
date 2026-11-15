# -*- coding: utf-8 -*-
"""The stepped agent boundary for Lander.

Five ports, each held for the one frame it is sent in: 0 fires the
engine, 1 and 2 turn left and right, 3 and 4 fire while turning left
and right. A frame with no port coasts. Green means landed: on the pad,
within the rung's limits for speed down and across (across the pad,
which may move) and for tilt.

Clocked: the craft flies whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class LanderEnv(TaskEnv):
    """Deterministic, stepped view of one Lander run."""

    task_class = ('neural_workshop.ui.lander', 'Lander')
    ports = 5
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_lander_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> LanderEnv:
    """A production environment: the task's own defaults."""
    return LanderEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_lander_outcome = LanderEnv.verifier()

__all__ = ['LanderEnv', 'make_lander_env', 'verify_lander_outcome']
