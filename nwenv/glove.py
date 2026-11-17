# -*- coding: utf-8 -*-
"""The stepped agent boundary for Glove.

Four ports: 0-3 move the glove up, down, left and right on the screen
as the camera now shows it, for the step they are sent in. Green
means the pitches were caught with no more misses than allowed.

Clocked: the pitches fly and the camera cuts whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class GloveEnv(TaskEnv):
    """Deterministic, stepped view of one Glove run."""

    task_class = ('neural_workshop.ui.glove', 'Glove')
    ports = 4
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_glove_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> GloveEnv:
    """A production environment: the task's own defaults."""
    return GloveEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_glove_outcome = GloveEnv.verifier()

__all__ = ['GloveEnv', 'make_glove_env',
           'verify_glove_outcome']
