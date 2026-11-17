# -*- coding: utf-8 -*-
"""The stepped agent boundary for Piano Man.

Twenty-six ports: port k presses key k, counted from the left (black
keys in their places; the low rungs have thirteen keys); port 25 asks
to hear the melody again, where that is allowed. The melody reaches
the agent only as sound. Green means every note was played in order.

Clocked: the melody plays, and the time to answer runs, whether or not the
agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class PianoManEnv(TaskEnv):
    """Deterministic, stepped view of one Piano Man run."""

    task_class = ('neural_workshop.ui.pianoman', 'PianoMan')
    ports = 26
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_piano_man_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> PianoManEnv:
    """A production environment: the task's own defaults."""
    return PianoManEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_piano_man_outcome = PianoManEnv.verifier()

__all__ = ['PianoManEnv', 'make_piano_man_env',
           'verify_piano_man_outcome']
