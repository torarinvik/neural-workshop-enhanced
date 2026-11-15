# -*- coding: utf-8 -*-
"""The stepped agent boundary for Catch.

Eight ports: 0-3 move the first basket left, right, nearer and
farther for the step they are sent in; 4-7 the second basket, on the
rungs that have two. Green means no more than one ball was dropped.
The agent hears the balls: each pops when thrown, whistles as it flies
from where it is, and thuds where it lands.

Clocked: the balls fly whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CatchEnv(TaskEnv):
    """Deterministic, stepped view of one Catch run."""

    task_class = ('neural_workshop.ui.catch', 'Catch')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_catch_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> CatchEnv:
    """A production environment: the task's own defaults."""
    return CatchEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_catch_outcome = CatchEnv.verifier()

__all__ = ['CatchEnv', 'make_catch_env',
           'verify_catch_outcome']
