# -*- coding: utf-8 -*-
"""The stepped agent boundary for Piano Tuner.

Five ports: 0 and 1 turn the tuning pin up and down, 2 and 3 turn it
finely, each for the step; 4 says it is in tune. Green means every
string was within the allowance when called done.

Clocked: the strings sound and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class PianoTunerEnv(TaskEnv):
    """Deterministic, stepped view of one Piano Tuner run."""

    task_class = ('neural_workshop.ui.pianotuner', 'PianoTuner')
    ports = 5
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_piano_tuner_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> PianoTunerEnv:
    """A production environment: the task's own defaults."""
    return PianoTunerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_piano_tuner_outcome = PianoTunerEnv.verifier()

__all__ = ['PianoTunerEnv', 'make_piano_tuner_env',
           'verify_piano_tuner_outcome']
