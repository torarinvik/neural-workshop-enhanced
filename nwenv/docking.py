# -*- coding: utf-8 -*-
"""The stepped agent boundary for Docking.

Twelve ports: 0-5 thrust left, right, down, up, forward and back;
6-11 turn left, right, down, up and roll left and right; each for the
step it is sent in. Green means the ship docked centred, square and
slow enough before the fuel ran out.

Clocked: the ship drifts whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class DockingEnv(TaskEnv):
    """Deterministic, stepped view of one Docking run."""

    task_class = ('neural_workshop.ui.docking', 'Docking')
    ports = 12
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_docking_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> DockingEnv:
    """A production environment: the task's own defaults."""
    return DockingEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_docking_outcome = DockingEnv.verifier()

__all__ = ['DockingEnv', 'make_docking_env',
           'verify_docking_outcome']
