# -*- coding: utf-8 -*-
"""The stepped agent boundary for Kitchen.

Thirteen ports send the cook to a station: 0-3 the crates, 4-5 the
boards, 6-8 the stoves, 9-10 the plates, 11 the pass, 12 the bin
(only the stations the kitchen has). Green means every ticket was
served (one may lapse below rung 10).

Clocked: the pans cook whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class KitchenEnv(TaskEnv):
    """Deterministic, stepped view of one Kitchen run."""

    task_class = ('neural_workshop.ui.kitchen', 'Kitchen')
    ports = 13
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_kitchen_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> KitchenEnv:
    """A production environment: the task's own defaults."""
    return KitchenEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_kitchen_outcome = KitchenEnv.verifier()

__all__ = ['KitchenEnv', 'make_kitchen_env', 'verify_kitchen_outcome']
