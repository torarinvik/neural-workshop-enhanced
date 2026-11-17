# -*- coding: utf-8 -*-
"""The stepped agent boundary for Top Card.

Seven ports: port k names the card numbered k+1.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TopCardEnv(TaskEnv):
    """Deterministic, stepped view of one Top Card run."""

    task_class = ('neural_workshop.ui.topcard', 'TopCard')
    ports = 7
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_top_card_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> TopCardEnv:
    """A production environment: the task's own defaults."""
    return TopCardEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_top_card_outcome = TopCardEnv.verifier()

__all__ = ['TopCardEnv', 'make_top_card_env',
           'verify_top_card_outcome']
