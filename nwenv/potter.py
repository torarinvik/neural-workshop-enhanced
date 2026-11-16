# -*- coding: utf-8 -*-
"""The stepped agent boundary for Potter's Wheel.

Seventeen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Port 14 spins the wheel faster, 15 slower, 16 wets the clay. With the
button down the pointer presses the band of clay it is beside in
towards the axis or draws it out. The agent hears the wheel, the clay
under the hand, a chime as each band comes right and a squeak when the
clay is dry.

Clocked: the wheel turns and the clay dries whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class PottersWheelEnv(TaskEnv):
    """Deterministic, stepped view of one Potter's Wheel run."""

    task_class = ('neural_workshop.ui.potter', 'PottersWheel')
    ports = 17
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_potters_wheel_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> PottersWheelEnv:
    """A production environment: the task's own defaults."""
    return PottersWheelEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_potters_wheel_outcome = PottersWheelEnv.verifier()

__all__ = ['PottersWheelEnv', 'make_potters_wheel_env',
           'verify_potters_wheel_outcome']
