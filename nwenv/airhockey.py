# -*- coding: utf-8 -*-
"""The stepped agent boundary for Air Hockey.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14 and 15, held, slide the bar that keeps your goal left and
right. Your mallet goes to where the pointer is on your half of the
table. The agent hears the puck on the mallets and the walls, from the
side it is on, and each goal.

Clocked: the puck and the other player move whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class AirHockeyEnv(TaskEnv):
    """Deterministic, stepped view of one Air Hockey run."""

    task_class = ('neural_workshop.ui.airhockey', 'AirHockey')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_air_hockey_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> AirHockeyEnv:
    """A production environment: the task's own defaults."""
    return AirHockeyEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_air_hockey_outcome = AirHockeyEnv.verifier()

__all__ = ['AirHockeyEnv', 'make_air_hockey_env',
           'verify_air_hockey_outcome']
