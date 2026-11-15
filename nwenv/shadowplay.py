# -*- coding: utf-8 -*-
"""The stepped agent boundary for Shadow Play.

Six ports, each turning the rod for the step it is sent in: 0 and 1
about the upright, 2 and 3 tipping it down and up, 4 and 5 rolling
it. Turns the rung does not allow do nothing. Green means the shadow
held inside the outline for a moment.

Clocked: the time runs, and on some rungs the outline and the lamp move,
whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ShadowPlayEnv(TaskEnv):
    """Deterministic, stepped view of one Shadow Play run."""

    task_class = ('neural_workshop.ui.shadowplay', 'ShadowPlay')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_shadow_play_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> ShadowPlayEnv:
    """A production environment: the task's own defaults."""
    return ShadowPlayEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_shadow_play_outcome = ShadowPlayEnv.verifier()

__all__ = ['ShadowPlayEnv', 'make_shadow_play_env',
           'verify_shadow_play_outcome']
