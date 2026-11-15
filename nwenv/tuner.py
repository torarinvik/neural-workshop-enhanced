# -*- coding: utf-8 -*-
"""The stepped agent boundary for Tuner.

Six ports: 0 and 1 turn the dial down and up for the step they are
sent in, 2 and 3 the same finely; 4 locks on to the station under the
needle; 5 plays the tune again. The tune and the radio reach the agent
only as sound. Green means it locked on to the station playing the
tune and stayed with it.

Clocked: the stations play and the time runs whether or not the agent
acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TunerEnv(TaskEnv):
    """Deterministic, stepped view of one Tuner run."""

    task_class = ('neural_workshop.ui.tuner', 'Tuner')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_tuner_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> TunerEnv:
    """A production environment: the task's own defaults."""
    return TunerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_tuner_outcome = TunerEnv.verifier()

__all__ = ['TunerEnv', 'make_tuner_env',
           'verify_tuner_outcome']
