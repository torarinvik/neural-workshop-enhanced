# -*- coding: utf-8 -*-
"""The stepped agent boundary for Parallel?.

Two ports: 0 says parallel, 1 not.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ParallelEnv(TaskEnv):
    """Deterministic, stepped view of one Parallel? run."""

    task_class = ('neural_workshop.ui.parallel', 'Parallel')
    ports = 2
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_parallel_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> ParallelEnv:
    """A production environment: the task's own defaults."""
    return ParallelEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_parallel_outcome = ParallelEnv.verifier()

__all__ = ['ParallelEnv', 'make_parallel_env',
           'verify_parallel_outcome']
