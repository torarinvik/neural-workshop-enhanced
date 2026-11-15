# -*- coding: utf-8 -*-
"""The stepped agent boundary for Firebreak.

Nine ports: 0-3 move the crew's cursor up, down, left and right, 4
digs a firebreak under it, 5-8 move it four cells at a time. Green
means the fire burned out (or was starved) without reaching the town.

Clocked: the fire spreads whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FirebreakEnv(TaskEnv):
    """Deterministic, stepped view of one Firebreak run."""

    task_class = ('neural_workshop.ui.firebreak', 'Firebreak')
    ports = 9
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_firebreak_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> FirebreakEnv:
    """A production environment: the task's own defaults."""
    return FirebreakEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_firebreak_outcome = FirebreakEnv.verifier()

__all__ = ['FirebreakEnv', 'make_firebreak_env', 'verify_firebreak_outcome']
