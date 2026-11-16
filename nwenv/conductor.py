# -*- coding: utf-8 -*-
"""The stepped agent boundary for Conductor.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Port 14 is louder and 15 softer. A downward flick of the pointer is a
beat; a click on a section on a beat brings it in or cuts it off. The
score of cues is written on the screen. The agent hears the orchestra:
the drum on every beat and each section that is playing.

Clocked: the music keeps its own time whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ConductorEnv(TaskEnv):
    """Deterministic, stepped view of one Conductor run."""

    task_class = ('neural_workshop.ui.conductor', 'Conductor')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_conductor_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> ConductorEnv:
    """A production environment: the task's own defaults."""
    return ConductorEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_conductor_outcome = ConductorEnv.verifier()

__all__ = ['ConductorEnv', 'make_conductor_env',
           'verify_conductor_outcome']
