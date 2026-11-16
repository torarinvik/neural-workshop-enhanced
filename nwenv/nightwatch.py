# -*- coding: utf-8 -*-
"""The stepped agent boundary for Night Watch.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14 and 15, held, turn the view left and right along the floor.
The torch is at the pointer; a click on a thief catches them, a click
on anyone else is a strike and a click on nobody wastes a whistle
blast. The orders are written on the screen. The agent hears every
footstep from the side it falls on.

Clocked: everyone walks whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class NightWatchEnv(TaskEnv):
    """Deterministic, stepped view of one Night Watch run."""

    task_class = ('neural_workshop.ui.nightwatch', 'NightWatch')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_night_watch_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> NightWatchEnv:
    """A production environment: the task's own defaults."""
    return NightWatchEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_night_watch_outcome = NightWatchEnv.verifier()

__all__ = ['NightWatchEnv', 'make_night_watch_env',
           'verify_night_watch_outcome']
