# -*- coding: utf-8 -*-
"""The stepped agent boundary for Notebook.

Thirteen ports. Ports 0-3 choose among the codes a question offers;
ports 4-11 copy the card in view onto notebook lines 1-8 (a line the
round's notebook does not have does nothing); port 12 moves past a card
that is not a question.

Green means every question in the round was answered right. There is no
par. The notebook is drawn on the screen and nowhere else: a learner
that writes a code down still has to read it back off the pixels.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

WRITE, NEXT = 4, 12


class NotebookEnv(TaskEnv):
    """Deterministic, stepped view of one Notebook run."""

    task_class = ('neural_workshop.ui.notebook', 'Notebook')
    ports = 13
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_notebook_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> NotebookEnv:
    """A production environment: the task's own defaults."""
    return NotebookEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_notebook_outcome = NotebookEnv.verifier()

__all__ = ['NEXT', 'NotebookEnv', 'WRITE', 'make_notebook_env',
           'verify_notebook_outcome']
