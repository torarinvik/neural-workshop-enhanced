# -*- coding: utf-8 -*-
"""The stepped agent boundary for Shadow Puppets.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14 and 15 roll the figure a little left and right. With the
button down, moving the pointer across spins the figure and up and
down tips it. On the low rungs the agent hears a tone that rises as
the shadow nears the one wanted, and a bell as each is cast.

Clocked: the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ShadowPuppetsEnv(TaskEnv):
    """Deterministic, stepped view of one Shadow Puppets run."""

    task_class = ('neural_workshop.ui.shadowpuppets', 'ShadowPuppets')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_shadow_puppets_env(seed: int = 0,
                              shm_name: Optional[str] = None) -> ShadowPuppetsEnv:
    """A production environment: the task's own defaults."""
    return ShadowPuppetsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_shadow_puppets_outcome = ShadowPuppetsEnv.verifier()

__all__ = ['ShadowPuppetsEnv', 'make_shadow_puppets_env',
           'verify_shadow_puppets_outcome']
