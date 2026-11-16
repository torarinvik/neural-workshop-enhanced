# -*- coding: utf-8 -*-
"""The stepped agent boundary for Why They Feel.

Eight ports. Port k picks answer k+1 of the buttons under the story. A chime
follows a right answer and a low note a wrong one.

Clocked: each item has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhyTheyFeelEnv(TaskEnv):
    """Deterministic, stepped view of one Why They Feel run."""

    task_class = ('neural_workshop.ui.whytheyfeel', 'WhyTheyFeel')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_why_they_feel_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> WhyTheyFeelEnv:
    """A production environment: the task's own defaults."""
    return WhyTheyFeelEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_why_they_feel_outcome = WhyTheyFeelEnv.verifier()

__all__ = ['WhyTheyFeelEnv', 'make_why_they_feel_env',
           'verify_why_they_feel_outcome']
