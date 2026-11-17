# -*- coding: utf-8 -*-
"""The stepped agent boundary for Will It Fit?.

Four ports: 0 says yes and 1 no; where there are holes to choose
from, port k picks hole k.

Turn-based, so it takes the think clock: the piece and holes stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WillItFitEnv(TaskEnv):
    """Deterministic, stepped view of one Will It Fit? run."""

    task_class = ('neural_workshop.ui.willitfit', 'WillItFit')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_will_it_fit_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> WillItFitEnv:
    """A production environment: the task's own defaults."""
    return WillItFitEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_will_it_fit_outcome = WillItFitEnv.verifier()

__all__ = ['WillItFitEnv', 'make_will_it_fit_env',
           'verify_will_it_fit_outcome']
