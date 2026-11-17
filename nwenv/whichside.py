# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Side?.

Two ports: 0 says the new panel belongs on the left, 1 on the right.

Turn-based, so it takes the think clock: the panels stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhichSideEnv(TaskEnv):
    """Deterministic, stepped view of one Which Side? run."""

    task_class = ('neural_workshop.ui.whichside', 'WhichSide')
    ports = 2
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_which_side_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> WhichSideEnv:
    """A production environment: the task's own defaults."""
    return WhichSideEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_which_side_outcome = WhichSideEnv.verifier()

__all__ = ['WhichSideEnv', 'make_which_side_env',
           'verify_which_side_outcome']
