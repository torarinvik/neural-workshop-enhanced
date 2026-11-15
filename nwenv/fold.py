# -*- coding: utf-8 -*-
"""The stepped agent boundary for Fold It.

Six ports, one per answer: a lettered face up to rung 3, a cube after.
A port past the answers the trial offers does nothing. Green means the
answer was right; there is no par.

Turn-based, so it takes the think clock: net and cubes stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FoldItEnv(TaskEnv):
    """Deterministic, stepped view of one Fold It run."""

    task_class = ('neural_workshop.ui.fold', 'FoldIt')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_fold_it_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> FoldItEnv:
    """A production environment: the task's own defaults."""
    return FoldItEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_fold_it_outcome = FoldItEnv.verifier()

__all__ = ['FoldItEnv', 'make_fold_it_env', 'verify_fold_it_outcome']
