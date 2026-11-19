# -*- coding: utf-8 -*-
"""The stepped agent boundary for the forgiving walks: a maze where a
wrong press wastes a step instead of ending the trial.

Turn-based, so these take the think clock: nothing moves until a port
is pressed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .taskenv import TaskEnv

UI = 'neural_workshop.ui.longwalk'


class _Rung(TaskEnv):
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class LongWayRoundEnv(_Rung):
    """Long Way Round: Four ports: up, down, left, right. Green means
    the goal was reached within the steps allowed; red means the steps
    ran out."""

    task_class = (UI, 'LongWayRound')
    ports = 4


class KeyAndDoorEnv(_Rung):
    """Key and Door: Four ports: up, down, left, right. Green means the
    key was fetched and the door reached within the steps allowed; red
    means the steps ran out."""

    task_class = (UI, 'KeyAndDoor')
    ports = 4


verify_long_way_round_outcome = LongWayRoundEnv.verifier()
verify_key_and_door_outcome = KeyAndDoorEnv.verifier()

__all__ = ['LongWayRoundEnv', 'KeyAndDoorEnv']
