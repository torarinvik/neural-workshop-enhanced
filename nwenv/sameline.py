# -*- coding: utf-8 -*-
"""The stepped agent boundary for Same Line?.

Six ports: 0 says yes and 1 no; where the question is which end,
port k picks end k, counted from the top.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SameLineEnv(TaskEnv):
    """Deterministic, stepped view of one Same Line? run."""

    task_class = ('neural_workshop.ui.sameline', 'SameLine')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_same_line_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> SameLineEnv:
    """A production environment: the task's own defaults."""
    return SameLineEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_same_line_outcome = SameLineEnv.verifier()

__all__ = ['SameLineEnv', 'make_same_line_env',
           'verify_same_line_outcome']
