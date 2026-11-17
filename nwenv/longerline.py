# -*- coding: utf-8 -*-
"""The stepped agent boundary for Longer Line.

Four ports: port k picks line k (left to right; between rails, port 0
is the lower line).

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class LongerLineEnv(TaskEnv):
    """Deterministic, stepped view of one Longer Line run."""

    task_class = ('neural_workshop.ui.longerline', 'LongerLine')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_longer_line_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> LongerLineEnv:
    """A production environment: the task's own defaults."""
    return LongerLineEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_longer_line_outcome = LongerLineEnv.verifier()

__all__ = ['LongerLineEnv', 'make_longer_line_env',
           'verify_longer_line_outcome']
