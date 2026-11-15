# -*- coding: utf-8 -*-
"""The stepped agent boundary for Inside or Out?.

Two ports: 0 answers Inside (Yes, for two dots), 1 Outside (No). Green
means the answer was right.

Turn-based, so it takes the think clock: the line stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class InsideOrOutEnv(TaskEnv):
    """Deterministic, stepped view of one Inside or Out? run."""

    task_class = ('neural_workshop.ui.inside', 'InsideOrOut')
    ports = 2
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_inside_or_out_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> InsideOrOutEnv:
    """A production environment: the task's own defaults."""
    return InsideOrOutEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_inside_or_out_outcome = InsideOrOutEnv.verifier()

__all__ = ['InsideOrOutEnv', 'make_inside_or_out_env',
           'verify_inside_or_out_outcome']
