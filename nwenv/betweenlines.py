# -*- coding: utf-8 -*-
"""The stepped agent boundary for Between the Lines.

Eight ports. Port k picks answer k+1 of the buttons under the text. A chime
follows a right answer and a low note a wrong one.

Clocked: each item has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BetweenTheLinesEnv(TaskEnv):
    """Deterministic, stepped view of one Between the Lines run."""

    task_class = ('neural_workshop.ui.betweenlines', 'BetweenTheLines')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_between_the_lines_env(seed: int = 0,
                                 shm_name: Optional[str] = None) -> BetweenTheLinesEnv:
    """A production environment: the task's own defaults."""
    return BetweenTheLinesEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_between_the_lines_outcome = BetweenTheLinesEnv.verifier()

__all__ = ['BetweenTheLinesEnv', 'make_between_the_lines_env',
           'verify_between_the_lines_outcome']
