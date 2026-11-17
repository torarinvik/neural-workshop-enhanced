# -*- coding: utf-8 -*-
"""The stepped agent boundary for Kerbside.

Two ports: 0 steps forward and 1 steps back, for the step they are
sent in. Green means the far kerb was reached without being struck.
The cars are heard, not seen.

Clocked: the traffic passes whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class KerbsideEnv(TaskEnv):
    """Deterministic, stepped view of one Kerbside run."""

    task_class = ('neural_workshop.ui.kerbside', 'Kerbside')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_kerbside_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> KerbsideEnv:
    """A production environment: the task's own defaults."""
    return KerbsideEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_kerbside_outcome = KerbsideEnv.verifier()

__all__ = ['KerbsideEnv', 'make_kerbside_env',
           'verify_kerbside_outcome']
