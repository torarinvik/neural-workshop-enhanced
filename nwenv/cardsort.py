# -*- coding: utf-8 -*-
"""The stepped agent boundary for Card Sort.

Four ports: port k puts the card under key card k. Green means it went
where the hidden rule says.

Turn-based, so it takes the think clock: the cards stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CardSortEnv(TaskEnv):
    """Deterministic, stepped view of one Card Sort run."""

    task_class = ('neural_workshop.ui.cardsort', 'CardSort')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_card_sort_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> CardSortEnv:
    """A production environment: the task's own defaults."""
    return CardSortEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_card_sort_outcome = CardSortEnv.verifier()

__all__ = ['CardSortEnv', 'make_card_sort_env',
           'verify_card_sort_outcome']
