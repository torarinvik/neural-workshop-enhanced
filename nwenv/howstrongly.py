# -*- coding: utf-8 -*-
"""The stepped agent boundary for How Strongly.

Eight ports. Port k picks answer k+1 of the buttons under the dialogue. A chime
follows a right answer and a low note a wrong one.
From rung 4 there are four answers to give, an intensity for each emotion.

Clocked: each item has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HowStronglyEnv(TaskEnv):
    """Deterministic, stepped view of one How Strongly run."""

    task_class = ('neural_workshop.ui.howstrongly', 'HowStrongly')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_how_strongly_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> HowStronglyEnv:
    """A production environment: the task's own defaults."""
    return HowStronglyEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_how_strongly_outcome = HowStronglyEnv.verifier()

__all__ = ['HowStronglyEnv', 'make_how_strongly_env',
           'verify_how_strongly_outcome']
