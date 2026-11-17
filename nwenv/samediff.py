# -*- coding: utf-8 -*-
"""The stepped agent boundary for Same or Different?.

Two ports: 0 says the same, 1 different. The pitch and rhythm guises
reach the agent only as sound.

Clocked: sounds play and the second thing follows the first whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SameDiffEnv(TaskEnv):
    """Deterministic, stepped view of one Same or Different? run."""

    task_class = ('neural_workshop.ui.samediff', 'SameDiff')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive', 'guise': 'guise'}


def make_same_or_different_env(seed: int = 0,
                                 shm_name: Optional[str] = None) -> SameDiffEnv:
    """A production environment: the task's own defaults."""
    return SameDiffEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_same_or_different_outcome = SameDiffEnv.verifier()

__all__ = ['SameDiffEnv', 'make_same_or_different_env',
           'verify_same_or_different_outcome']
