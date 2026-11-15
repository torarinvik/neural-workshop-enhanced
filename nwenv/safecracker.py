# -*- coding: utf-8 -*-
"""The stepped agent boundary for Safecracker.

Forty-one ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-39 type
the letters A to Z and port 40 is Backspace. Dragging round the dial
turns it; letting go on the number the next tumbler wants, having come
to it the right way, sets the tumbler. Dragging the handle down opens
the door once the tumblers are set and the word is typed. The agent
hears every tick and thunk.

Clocked: the alarm counts down, the door swings and the camera drifts whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SafecrackerEnv(TaskEnv):
    """Deterministic, stepped view of one Safecracker run."""

    task_class = ('neural_workshop.ui.safecracker', 'Safecracker')
    ports = 41
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_safecracker_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> SafecrackerEnv:
    """A production environment: the task's own defaults."""
    return SafecrackerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_safecracker_outcome = SafecrackerEnv.verifier()

__all__ = ['SafecrackerEnv', 'make_safecracker_env',
           'verify_safecracker_outcome']
