# -*- coding: utf-8 -*-
"""The stepped agent boundary for Analogies.

Eight ports: port k picks candidate k (only as many as the rung shows).

Turn-based, so it takes the think clock: the panels stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class AnalogyEnv(TaskEnv):
    """Deterministic, stepped view of one Analogies run."""

    task_class = ('neural_workshop.ui.analogy', 'Analogy')
    ports = 8
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_analogies_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> AnalogyEnv:
    """A production environment: the task's own defaults."""
    return AnalogyEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_analogies_outcome = AnalogyEnv.verifier()

__all__ = ['AnalogyEnv', 'make_analogies_env',
           'verify_analogies_outcome']
