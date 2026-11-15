# -*- coding: utf-8 -*-
"""The stepped agent boundary for Crane.

Five ports: 0 and 1 drive the trolley left and right for the step,
2 and 3 hoist the hook up and down, 4 grabs the container under the
hook or sets the carried one down. Green means every container reached
the bay of its colour with nothing struck or dropped hard.

Clocked: the load swings whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CraneEnv(TaskEnv):
    """Deterministic, stepped view of one Crane run."""

    task_class = ('neural_workshop.ui.crane', 'Crane')
    ports = 5
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_crane_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> CraneEnv:
    """A production environment: the task's own defaults."""
    return CraneEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_crane_outcome = CraneEnv.verifier()

__all__ = ['CraneEnv', 'make_crane_env',
           'verify_crane_outcome']
