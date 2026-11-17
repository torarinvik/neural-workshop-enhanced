# -*- coding: utf-8 -*-
"""The stepped agent boundary for Behind the Screen.

Nine ports: port k answers k.

Clocked: the balls roll whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BehindScreenEnv(TaskEnv):
    """Deterministic, stepped view of one Behind the Screen run."""

    task_class = ('neural_workshop.ui.behindscreen', 'BehindScreen')
    ports = 9
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_behind_the_screen_env(seed: int = 0,
                                 shm_name: Optional[str] = None) -> BehindScreenEnv:
    """A production environment: the task's own defaults."""
    return BehindScreenEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_behind_the_screen_outcome = BehindScreenEnv.verifier()

__all__ = ['BehindScreenEnv', 'make_behind_the_screen_env',
           'verify_behind_the_screen_outcome']
