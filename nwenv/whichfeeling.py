# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Feeling.

Eight ports. Port k picks answer k+1 of the buttons under the comment. A chime
follows a right answer and a low note a wrong one.

Clocked: each item has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhichFeelingEnv(TaskEnv):
    """Deterministic, stepped view of one Which Feeling run."""

    task_class = ('neural_workshop.ui.whichfeeling', 'WhichFeeling')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_which_feeling_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> WhichFeelingEnv:
    """A production environment: the task's own defaults."""
    return WhichFeelingEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_which_feeling_outcome = WhichFeelingEnv.verifier()

__all__ = ['WhichFeelingEnv', 'make_which_feeling_env',
           'verify_which_feeling_outcome']
