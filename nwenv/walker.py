# -*- coding: utf-8 -*-
"""The stepped agent boundary for Walker.

Two ports: 0 says the figure faces left, 1 right.

Clocked: the scene plays and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WalkerEnv(TaskEnv):
    """Deterministic, stepped view of one Walker run."""

    task_class = ('neural_workshop.ui.walker', 'Walker')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_walker_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> WalkerEnv:
    """A production environment: the task's own defaults."""
    return WalkerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_walker_outcome = WalkerEnv.verifier()

__all__ = ['WalkerEnv', 'make_walker_env',
           'verify_walker_outcome']
