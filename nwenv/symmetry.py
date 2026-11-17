# -*- coding: utf-8 -*-
"""The stepped agent boundary for Symmetric?.

Two ports: 0 says yes, 1 no.

Turn-based, so it takes the think clock: the pattern stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SymmetryEnv(TaskEnv):
    """Deterministic, stepped view of one Symmetric? run."""

    task_class = ('neural_workshop.ui.symmetry', 'Symmetry')
    ports = 2
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_symmetric_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> SymmetryEnv:
    """A production environment: the task's own defaults."""
    return SymmetryEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_symmetric_outcome = SymmetryEnv.verifier()

__all__ = ['SymmetryEnv', 'make_symmetric_env',
           'verify_symmetric_outcome']
