# -*- coding: utf-8 -*-
"""The stepped agent boundary for Drone Hoops.

Ten ports, each a push for the step it is sent in, relative to the
camera: 0 forward (into the screen), 1 back, 2 left, 3 right, 4-7 the
diagonals forward-left, forward-right, back-left, back-right; 8 up and
9 down. The camera changes, so the same port flies a different way
after a cut. The agent hears the bell on the next hoop (faster when
near, higher when above, panned to its side of the screen), the rotors,
the wind before a gust, birds and thunder.

Clocked: the hoops turn, the wind blows and the clock runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class DroneHoopsEnv(TaskEnv):
    """Deterministic, stepped view of one Drone Hoops run."""

    task_class = ('neural_workshop.ui.dronehoops', 'DroneHoops')
    ports = 10
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_drone_hoops_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> DroneHoopsEnv:
    """A production environment: the task's own defaults."""
    return DroneHoopsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_drone_hoops_outcome = DroneHoopsEnv.verifier()

__all__ = ['DroneHoopsEnv', 'make_drone_hoops_env',
           'verify_drone_hoops_outcome']
