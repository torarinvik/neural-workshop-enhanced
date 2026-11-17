# -*- coding: utf-8 -*-
"""The stepped agent boundary for Pecking Order.

Twelve ports: 0 says the left one wins and 1 the right; when the
question is a place in the order, port k picks creature k.

Turn-based, so it takes the think clock: the clues stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class PeckingOrderEnv(TaskEnv):
    """Deterministic, stepped view of one Pecking Order run."""

    task_class = ('neural_workshop.ui.peckingorder', 'PeckingOrder')
    ports = 12
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_pecking_order_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> PeckingOrderEnv:
    """A production environment: the task's own defaults."""
    return PeckingOrderEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_pecking_order_outcome = PeckingOrderEnv.verifier()

__all__ = ['PeckingOrderEnv', 'make_pecking_order_env',
           'verify_pecking_order_outcome']
