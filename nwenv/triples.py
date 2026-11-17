# -*- coding: utf-8 -*-
"""The stepped agent boundary for Triples.

Six ports: port k picks candidate k, or answers k triples.

Turn-based, so it takes the think clock: the cards stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TriplesEnv(TaskEnv):
    """Deterministic, stepped view of one Triples run."""

    task_class = ('neural_workshop.ui.triples', 'Triples')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_triples_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> TriplesEnv:
    """A production environment: the task's own defaults."""
    return TriplesEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_triples_outcome = TriplesEnv.verifier()

__all__ = ['TriplesEnv', 'make_triples_env',
           'verify_triples_outcome']
