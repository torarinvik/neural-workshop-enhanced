# -*- coding: utf-8 -*-
"""The stepped agent boundary for Balance.

Four ports: 0-3 push the cart left, right, away and near for one step.
Green means every flag was collected in turn -- the cart held still
under it with the pole up -- before the time ran out, the lantern on
the pole's top never touching the ground.

Clocked: the pole falls whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BalanceEnv(TaskEnv):
    """Deterministic, stepped view of one Balance run."""

    task_class = ('neural_workshop.ui.balance', 'Balance')
    ports = 4
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_balance_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> BalanceEnv:
    """A production environment: the task's own defaults."""
    return BalanceEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_balance_outcome = BalanceEnv.verifier()

__all__ = ['BalanceEnv', 'make_balance_env',
           'verify_balance_outcome']
