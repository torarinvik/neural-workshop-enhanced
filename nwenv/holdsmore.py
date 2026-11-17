# -*- coding: utf-8 -*-
"""The stepped agent boundary for Holds More.

Four ports: port k picks container k, or mark k when water is poured.

Turn-based, so it takes the think clock: the containers stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HoldsMoreEnv(TaskEnv):
    """Deterministic, stepped view of one Holds More run."""

    task_class = ('neural_workshop.ui.holdsmore', 'HoldsMore')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_holds_more_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> HoldsMoreEnv:
    """A production environment: the task's own defaults."""
    return HoldsMoreEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_holds_more_outcome = HoldsMoreEnv.verifier()

__all__ = ['HoldsMoreEnv', 'make_holds_more_env',
           'verify_holds_more_outcome']
