# -*- coding: utf-8 -*-
"""The stepped agent boundary for Touching?.

Six ports: 0-2 answer Apart, Touching, Overlapping for a pair; when
pairs are counted, 0-5 answer that many. Green means the answer was
right.

Turn-based, so it takes the think clock: the shapes stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TouchingEnv(TaskEnv):
    """Deterministic, stepped view of one Touching? run."""

    task_class = ('neural_workshop.ui.touching', 'Touching')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_touching_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> TouchingEnv:
    """A production environment: the task's own defaults."""
    return TouchingEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_touching_outcome = TouchingEnv.verifier()

__all__ = ['TouchingEnv', 'make_touching_env',
           'verify_touching_outcome']
