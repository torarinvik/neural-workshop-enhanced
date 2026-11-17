# -*- coding: utf-8 -*-
"""The stepped agent boundary for Rover.

Four ports: 0 drives, 1 brakes and backs up, 2 and 3 steer left and
right, each for the step it is sent in and applied when the signal
arrives. Green means every flag was reached without hitting a rock or
tipping over.

Clocked: the rover rolls on and the signal travels whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class RoverEnv(TaskEnv):
    """Deterministic, stepped view of one Rover run."""

    task_class = ('neural_workshop.ui.rover', 'Rover')
    ports = 4
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_rover_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> RoverEnv:
    """A production environment: the task's own defaults."""
    return RoverEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_rover_outcome = RoverEnv.verifier()

__all__ = ['RoverEnv', 'make_rover_env',
           'verify_rover_outcome']
