# -*- coding: utf-8 -*-
"""The stepped agent boundary for Ferry.

Six ports, each for one step: 0 ahead, 1 astern, 2 turn left, 3 turn
right, 4 ahead and left, 5 ahead and right. Green means every
crossing was made, docking at each lit pier, with no barge struck.

Clocked: the river and the barges move whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FerryEnv(TaskEnv):
    """Deterministic, stepped view of one Ferry run."""

    task_class = ('neural_workshop.ui.ferry', 'Ferry')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_ferry_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> FerryEnv:
    """A production environment: the task's own defaults."""
    return FerryEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_ferry_outcome = FerryEnv.verifier()

__all__ = ['FerryEnv', 'make_ferry_env',
           'verify_ferry_outcome']
