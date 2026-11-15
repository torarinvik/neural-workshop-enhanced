# -*- coding: utf-8 -*-
"""The stepped agent boundary for Stagehand.

Nineteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-18 are
the cue keys: L lights, C curtain, M music, S smoke, T thunder. A drag
that starts on a prop moves it to the mark it is let go over; a click
on a prop puts the spotlight on it. The agent hears the bell, the drum,
the whistle and the actor's steps.

Clocked: cues sound, the actor walks, the camera cuts and a line's moment passes whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class StagehandEnv(TaskEnv):
    """Deterministic, stepped view of one Stagehand run."""

    task_class = ('neural_workshop.ui.stagehand', 'Stagehand')
    ports = 19
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_stagehand_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> StagehandEnv:
    """A production environment: the task's own defaults."""
    return StagehandEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_stagehand_outcome = StagehandEnv.verifier()

__all__ = ['StagehandEnv', 'make_stagehand_env',
           'verify_stagehand_outcome']
