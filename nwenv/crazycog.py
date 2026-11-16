# -*- coding: utf-8 -*-
"""The stepped agent boundary for Crazy Cog.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Port 14 clears the board and 15 switches between the front and back
layers. A cog dragged from
the tray onto the board snaps into mesh with the cogs beside it or onto
an axle, or onto the axle of a cog on the other layer; a chain is
dragged onto one cog and clicked onto another. The agent hears each cog go down (higher when it meshes), the
motor's hum rising with its speed and groaning when it stalls, a grind
when the train jams, the fan, and the winch ticking as the bucket rises.

Clocked: the motor turns and the clock runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CrazyCogEnv(TaskEnv):
    """Deterministic, stepped view of one Crazy Cog run."""

    task_class = ('neural_workshop.ui.crazycog', 'CrazyCog')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_crazy_cog_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> CrazyCogEnv:
    """A production environment: the task's own defaults."""
    return CrazyCogEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_crazy_cog_outcome = CrazyCogEnv.verifier()

__all__ = ['CrazyCogEnv', 'make_crazy_cog_env',
           'verify_crazy_cog_outcome']
