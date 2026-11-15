# -*- coding: utf-8 -*-
"""The stepped agent boundary for Juggler.

Two ports: 0 and 1 push the tray left and right for one step;
sending nothing brakes it. Green means no ball reached the floor before
the act ended.

Clocked: the balls fall whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class JugglerEnv(TaskEnv):
    """Deterministic, stepped view of one Juggler run."""

    task_class = ('neural_workshop.ui.juggler', 'Juggler')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_juggler_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> JugglerEnv:
    """A production environment: the task's own defaults."""
    return JugglerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_juggler_outcome = JugglerEnv.verifier()

__all__ = ['JugglerEnv', 'make_juggler_env',
           'verify_juggler_outcome']
