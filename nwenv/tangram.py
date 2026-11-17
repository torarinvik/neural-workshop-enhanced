# -*- coding: utf-8 -*-
"""The stepped agent boundary for Tangram.

Four ports: port k picks set k.

Turn-based, so it takes the think clock: the pieces stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TangramEnv(TaskEnv):
    """Deterministic, stepped view of one Tangram run."""

    task_class = ('neural_workshop.ui.tangram', 'Tangram')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_tangram_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> TangramEnv:
    """A production environment: the task's own defaults."""
    return TangramEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_tangram_outcome = TangramEnv.verifier()

__all__ = ['TangramEnv', 'make_tangram_env',
           'verify_tangram_outcome']
