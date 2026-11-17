# -*- coding: utf-8 -*-
"""The stepped agent boundary for Number Line.

Six ports: port k picks answer k (the numbers rise from the left),
or mark k.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class NumberLineEnv(TaskEnv):
    """Deterministic, stepped view of one Number Line run."""

    task_class = ('neural_workshop.ui.numberline', 'NumberLine')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_number_line_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> NumberLineEnv:
    """A production environment: the task's own defaults."""
    return NumberLineEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_number_line_outcome = NumberLineEnv.verifier()

__all__ = ['NumberLineEnv', 'make_number_line_env',
           'verify_number_line_outcome']
