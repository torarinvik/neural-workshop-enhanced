# -*- coding: utf-8 -*-
"""The stepped agent boundary for Tightrope.

Fifteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Port 14 takes a step. The pointer left and right carries the balancing
pole; a click on a bird that has landed on the pole shoos it. The agent
hears each step, the wind a second before it blows, from the side it
comes from, the birds, and the wire creak when the lean is large.

Clocked: the walker tips whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TightropeEnv(TaskEnv):
    """Deterministic, stepped view of one Tightrope run."""

    task_class = ('neural_workshop.ui.tightrope', 'Tightrope')
    ports = 15
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_tightrope_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> TightropeEnv:
    """A production environment: the task's own defaults."""
    return TightropeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_tightrope_outcome = TightropeEnv.verifier()

__all__ = ['TightropeEnv', 'make_tightrope_env',
           'verify_tightrope_outcome']
