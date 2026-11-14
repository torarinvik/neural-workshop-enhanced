# -*- coding: utf-8 -*-
"""The stepped agent boundary for Will It Fall?.

Eight ports, one per answer; a port past the answers the question offers
does nothing. Green means the answer was right. There is no par.

Turn-based, so it takes the think clock: every scene is a still
picture, the ball's motion given as a trail of dots at equal moments.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WillItFallEnv(TaskEnv):
    """Deterministic, stepped view of one Will It Fall? run."""

    task_class = ('neural_workshop.ui.falls', 'WillItFall')
    ports = 8
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_will_it_fall_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> WillItFallEnv:
    """A production environment: the task's own defaults."""
    return WillItFallEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_will_it_fall_outcome = WillItFallEnv.verifier()

__all__ = ['WillItFallEnv', 'make_will_it_fall_env',
           'verify_will_it_fall_outcome']
