# -*- coding: utf-8 -*-
"""The stepped agent boundary for Longer or Sooner?.

Two ports: 0 says the first (or the left), 1 the second (or the
right). The tones reach the agent only as sound.

Clocked: the lights and tones play whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HowLongEnv(TaskEnv):
    """Deterministic, stepped view of one Longer or Sooner? run."""

    task_class = ('neural_workshop.ui.howlong', 'HowLong')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_longer_or_sooner_env(seed: int = 0,
                                shm_name: Optional[str] = None) -> HowLongEnv:
    """A production environment: the task's own defaults."""
    return HowLongEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_longer_or_sooner_outcome = HowLongEnv.verifier()

__all__ = ['HowLongEnv', 'make_longer_or_sooner_env',
           'verify_longer_or_sooner_outcome']
