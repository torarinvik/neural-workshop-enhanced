# -*- coding: utf-8 -*-
"""The stepped agent boundary for Bartender.

Fifteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Port 14 puts ice in the glass or takes it out. Holding a bottle over
the glass pours; dragging the glass back and letting go slides it
along the bar, further for a longer pull. The orders are written on
the screen. The agent hears the pour rise in pitch as the glass fills,
the ice, the slide, a served customer and a broken glass.

Clocked: customers arrive and walk out whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BartenderEnv(TaskEnv):
    """Deterministic, stepped view of one Bartender run."""

    task_class = ('neural_workshop.ui.bartender', 'Bartender')
    ports = 15
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_bartender_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> BartenderEnv:
    """A production environment: the task's own defaults."""
    return BartenderEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_bartender_outcome = BartenderEnv.verifier()

__all__ = ['BartenderEnv', 'make_bartender_env',
           'verify_bartender_outcome']
