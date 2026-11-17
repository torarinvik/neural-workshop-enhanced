# -*- coding: utf-8 -*-
"""The stepped agent boundary for Odd One Out.

Eight ports: port k picks panel k.

Turn-based, so it takes the think clock: the panels stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class OddOneOutEnv(TaskEnv):
    """Deterministic, stepped view of one Odd One Out run."""

    task_class = ('neural_workshop.ui.oddoneout', 'OddOneOut')
    ports = 8
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_odd_one_out_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> OddOneOutEnv:
    """A production environment: the task's own defaults."""
    return OddOneOutEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_odd_one_out_outcome = OddOneOutEnv.verifier()

__all__ = ['OddOneOutEnv', 'make_odd_one_out_env',
           'verify_odd_one_out_outcome']
