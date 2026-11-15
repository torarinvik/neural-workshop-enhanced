# -*- coding: utf-8 -*-
"""The stepped agent boundary for Keep the Beat.

One port: 0 taps. Green means enough of the beats after the metronome
fell silent were each met by a tap close enough to them, with few taps
off the beat. Each frame carries the clicks heard since the last.

Clocked: the beat goes on whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class KeepTheBeatEnv(TaskEnv):
    """Deterministic, stepped view of one Keep the Beat run."""

    task_class = ('neural_workshop.ui.beat', 'KeepTheBeat')
    ports = 1
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_keep_the_beat_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> KeepTheBeatEnv:
    """A production environment: the task's own defaults."""
    return KeepTheBeatEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_keep_the_beat_outcome = KeepTheBeatEnv.verifier()

__all__ = ['KeepTheBeatEnv', 'make_keep_the_beat_env',
           'verify_keep_the_beat_outcome']
