# -*- coding: utf-8 -*-
"""The stepped agent boundary for Bigger Area.

Four ports: port k picks shape k, from the left.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BiggerAreaEnv(TaskEnv):
    """Deterministic, stepped view of one Bigger Area run."""

    task_class = ('neural_workshop.ui.biggerarea', 'BiggerArea')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_bigger_area_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> BiggerAreaEnv:
    """A production environment: the task's own defaults."""
    return BiggerAreaEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_bigger_area_outcome = BiggerAreaEnv.verifier()

__all__ = ['BiggerAreaEnv', 'make_bigger_area_env',
           'verify_bigger_area_outcome']
