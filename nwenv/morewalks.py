# -*- coding: utf-8 -*-
"""The stepped agent boundary for the more forgiving walks: a box to
push and pull, one-way openings, and ice; a wrong press wastes a step
instead of ending the trial.

Turn-based, so these take the think clock: nothing moves until a port
is pressed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .taskenv import TaskEnv

UI = 'neural_workshop.ui.morewalks'


class _Rung(TaskEnv):
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class PushAndPullEnv(_Rung):
    """Push and Pull: Four ports: up, down, left, right. Green means the
    box was brought onto the mark within the steps allowed; red means
    the steps ran out."""

    task_class = (UI, 'PushAndPull')
    ports = 4


class OneWayDoorsEnv(_Rung):
    """One-Way Doors: Four ports: up, down, left, right. Green means the
    goal was reached within the steps allowed; red means the steps ran
    out."""

    task_class = (UI, 'OneWayDoors')
    ports = 4


class IceFloorEnv(_Rung):
    """Ice Floor: Four ports: up, down, left, right, each sliding the
    player until something stops it. Green means a stop on the goal
    within the steps allowed; red means the steps ran out."""

    task_class = (UI, 'IceFloor')
    ports = 4


verify_push_and_pull_outcome = PushAndPullEnv.verifier()
verify_one_way_doors_outcome = OneWayDoorsEnv.verifier()
verify_ice_floor_outcome = IceFloorEnv.verifier()

__all__ = ['PushAndPullEnv', 'OneWayDoorsEnv', 'IceFloorEnv']
