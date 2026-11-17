# -*- coding: utf-8 -*-
"""The stepped agent boundary for Who Lives Where?.

Six ports: port k picks house k, counted from the left.

Turn-based, so it takes the think clock: the clues stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ZebraEnv(TaskEnv):
    """Deterministic, stepped view of one Who Lives Where? run."""

    task_class = ('neural_workshop.ui.zebra', 'Zebra')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_who_lives_where_env(seed: int = 0,
                               shm_name: Optional[str] = None) -> ZebraEnv:
    """A production environment: the task's own defaults."""
    return ZebraEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_who_lives_where_outcome = ZebraEnv.verifier()

__all__ = ['ZebraEnv', 'make_who_lives_where_env',
           'verify_who_lives_where_outcome']
