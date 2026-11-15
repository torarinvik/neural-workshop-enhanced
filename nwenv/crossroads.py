# -*- coding: utf-8 -*-
"""The stepped agent boundary for Crossroads.

Four ports: 0-3 switch junctions 1-4 between their two ways (only as
many as the town has); a switch runs through amber and all-red. Green
means the shift ended with no gridlock and no ambulance held up.

Clocked: the traffic comes whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CrossroadsEnv(TaskEnv):
    """Deterministic, stepped view of one Crossroads run."""

    task_class = ('neural_workshop.ui.crossroads', 'Crossroads')
    ports = 4
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_crossroads_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> CrossroadsEnv:
    """A production environment: the task's own defaults."""
    return CrossroadsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_crossroads_outcome = CrossroadsEnv.verifier()

__all__ = ['CrossroadsEnv', 'make_crossroads_env',
           'verify_crossroads_outcome']
