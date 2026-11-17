# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Way.

Eight ports: 0 left, 1 right, 2 up, 3 down, 4 up left, 5 up right,
6 down left, 7 down right (only as many as the rung asks).

Clocked: the scene plays and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhichWayEnv(TaskEnv):
    """Deterministic, stepped view of one Which Way run."""

    task_class = ('neural_workshop.ui.whichway', 'WhichWay')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_which_way_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> WhichWayEnv:
    """A production environment: the task's own defaults."""
    return WhichWayEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_which_way_outcome = WhichWayEnv.verifier()

__all__ = ['WhichWayEnv', 'make_which_way_env',
           'verify_which_way_outcome']
