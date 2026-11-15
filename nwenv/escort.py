# -*- coding: utf-8 -*-
"""The stepped agent boundary for Escort.

Six ports: 0-5 pull levers 1-6 (only as many as the temple has);
every device wearing that lever's gem flips. Green means every walker
reached the east gate.

Clocked: the walkers walk whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class EscortEnv(TaskEnv):
    """Deterministic, stepped view of one Escort run."""

    task_class = ('neural_workshop.ui.escort', 'Escort')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_escort_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> EscortEnv:
    """A production environment: the task's own defaults."""
    return EscortEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_escort_outcome = EscortEnv.verifier()

__all__ = ['EscortEnv', 'make_escort_env', 'verify_escort_outcome']
