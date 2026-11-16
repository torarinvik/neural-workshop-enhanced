# -*- coding: utf-8 -*-
"""The stepped agent boundary for Lock Pick.

Fifteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Port 14, held, tightens the tension wrench, which slackens when it is
let go. With the button down under a pin the pointer lifts it. The
agent hears the wrench slip, a tick at each pin touched (lower for the
one that binds), a tone that rises as the binding pin nears its
height, and the click of a pin setting.

Clocked: the tension falls away and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class LockPickEnv(TaskEnv):
    """Deterministic, stepped view of one Lock Pick run."""

    task_class = ('neural_workshop.ui.lockpick', 'LockPick')
    ports = 15
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_lock_pick_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> LockPickEnv:
    """A production environment: the task's own defaults."""
    return LockPickEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_lock_pick_outcome = LockPickEnv.verifier()

__all__ = ['LockPickEnv', 'make_lock_pick_env',
           'verify_lock_pick_outcome']
