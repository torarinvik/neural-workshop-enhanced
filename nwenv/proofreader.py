# -*- coding: utf-8 -*-
"""The stepped agent boundary for The Proofreader.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. A word dragged along
its line moves there; a sentence dragged by its number moves up or
down; a word clicked shows the forms it could take, and one clicked goes
in. Port 14 hands the passage in and port 15 puts the damage back. The
sounds are the same for a right fix and a wrong one.

Clocked: the clock runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ProofreaderEnv(TaskEnv):
    """Deterministic, stepped view of one The Proofreader run."""

    task_class = ('neural_workshop.ui.proofreader', 'Proofreader')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_proofreader_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> ProofreaderEnv:
    """A production environment: the task's own defaults."""
    return ProofreaderEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_proofreader_outcome = ProofreaderEnv.verifier()

__all__ = ['ProofreaderEnv', 'make_proofreader_env',
           'verify_proofreader_outcome']
