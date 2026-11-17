# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Ear.

Two ports: 0 says left, 1 right. The tones reach the agent only as
sound.

Clocked: the sounds play and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhichEarEnv(TaskEnv):
    """Deterministic, stepped view of one Which Ear run."""

    task_class = ('neural_workshop.ui.whichear', 'WhichEar')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_which_ear_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> WhichEarEnv:
    """A production environment: the task's own defaults."""
    return WhichEarEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_which_ear_outcome = WhichEarEnv.verifier()

__all__ = ['WhichEarEnv', 'make_which_ear_env',
           'verify_which_ear_outcome']
