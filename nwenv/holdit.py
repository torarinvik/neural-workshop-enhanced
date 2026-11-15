# -*- coding: utf-8 -*-
"""The stepped agent boundary for Hold It.

One port: 0 holds for the step it is sent in; send it every step to
keep holding, stop to let go. Green means the hold lasted the time asked
for, within a share of it. Each frame carries the sound since the last.

Clocked: the lamp shines and the turn comes whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HoldItEnv(TaskEnv):
    """Deterministic, stepped view of one Hold It run."""

    task_class = ('neural_workshop.ui.holdit', 'HoldIt')
    ports = 1
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_hold_it_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> HoldItEnv:
    """A production environment: the task's own defaults."""
    return HoldItEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_hold_it_outcome = HoldItEnv.verifier()

__all__ = ['HoldItEnv', 'make_hold_it_env',
           'verify_hold_it_outcome']
