# -*- coding: utf-8 -*-
"""The stepped agent boundary for Louder.

Three ports: port k says tone k was the loudest. The tones reach the
agent only as sound.

Clocked: the sounds play and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class LouderEnv(TaskEnv):
    """Deterministic, stepped view of one Louder run."""

    task_class = ('neural_workshop.ui.louder', 'Louder')
    ports = 3
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_louder_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> LouderEnv:
    """A production environment: the task's own defaults."""
    return LouderEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_louder_outcome = LouderEnv.verifier()

__all__ = ['LouderEnv', 'make_louder_env',
           'verify_louder_outcome']
