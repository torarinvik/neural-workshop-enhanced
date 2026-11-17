# -*- coding: utf-8 -*-
"""The stepped agent boundary for Bad Argument.

Eight ports. Port k picks answer k+1 of the buttons under the text. A chime
follows a right answer and a low note a wrong one.

Clocked: each item has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BadArgumentEnv(TaskEnv):
    """Deterministic, stepped view of one Bad Argument run."""

    task_class = ('neural_workshop.ui.badargument', 'BadArgument')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_bad_argument_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> BadArgumentEnv:
    """A production environment: the task's own defaults."""
    return BadArgumentEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_bad_argument_outcome = BadArgumentEnv.verifier()

__all__ = ['BadArgumentEnv', 'make_bad_argument_env',
           'verify_bad_argument_outcome']
