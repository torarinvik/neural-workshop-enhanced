# -*- coding: utf-8 -*-
"""The stepped agent boundary for Loading Dock.

Twenty ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-19 drive the
forklift for the step they are sent in: forward, back, turn left, turn
right, forward-left, forward-right, all relative to the forklift. A
drag from a shelf bay the forklift is beside to the forklift picks a
crate up; a drag from the forklift to a truck it is beside loads it; a
click on a truck's lamp sends the truck. The agent hears each truck's
horn before it leaves, the engine and the reversing beeper.

Clocked: trucks arrive and leave, the camera cuts and the other forklift works whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class LoadingDockEnv(TaskEnv):
    """Deterministic, stepped view of one Loading Dock run."""

    task_class = ('neural_workshop.ui.loadingdock', 'LoadingDock')
    ports = 20
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_loading_dock_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> LoadingDockEnv:
    """A production environment: the task's own defaults."""
    return LoadingDockEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_loading_dock_outcome = LoadingDockEnv.verifier()

__all__ = ['LoadingDockEnv', 'make_loading_dock_env',
           'verify_loading_dock_outcome']
