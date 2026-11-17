# -*- coding: utf-8 -*-
"""The stepped agent boundary for Heavier.

Eight ports: 0-3 push crate 1-4 for the step they are sent in; 4-7
answer crate 1-4. Green means every board was answered right.

Clocked: the crates slide and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HeavierEnv(TaskEnv):
    """Deterministic, stepped view of one Heavier run."""

    task_class = ('neural_workshop.ui.heavier', 'Heavier')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_heavier_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> HeavierEnv:
    """A production environment: the task's own defaults."""
    return HeavierEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_heavier_outcome = HeavierEnv.verifier()

__all__ = ['HeavierEnv', 'make_heavier_env',
           'verify_heavier_outcome']
