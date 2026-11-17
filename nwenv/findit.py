# -*- coding: utf-8 -*-
"""The stepped agent boundary for Find It.

Two ports: 0 says the target was there, 1 not.

Clocked: the crowd is covered after its time whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FindItEnv(TaskEnv):
    """Deterministic, stepped view of one Find It run."""

    task_class = ('neural_workshop.ui.findit', 'FindIt')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_find_it_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> FindItEnv:
    """A production environment: the task's own defaults."""
    return FindItEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_find_it_outcome = FindItEnv.verifier()

__all__ = ['FindItEnv', 'make_find_it_env',
           'verify_find_it_outcome']
