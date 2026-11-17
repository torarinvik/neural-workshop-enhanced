# -*- coding: utf-8 -*-
"""The stepped agent boundary for More or Less.

Three ports: 0 says the left (or the left colour), 1 the right, 2 the
same.

Clocked: the flash runs out whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class MoreOrLessEnv(TaskEnv):
    """Deterministic, stepped view of one More or Less run."""

    task_class = ('neural_workshop.ui.moreorless', 'MoreOrLess')
    ports = 3
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_more_or_less_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> MoreOrLessEnv:
    """A production environment: the task's own defaults."""
    return MoreOrLessEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_more_or_less_outcome = MoreOrLessEnv.verifier()

__all__ = ['MoreOrLessEnv', 'make_more_or_less_env',
           'verify_more_or_less_outcome']
