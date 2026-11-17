# -*- coding: utf-8 -*-
"""The stepped agent boundary for By Ear.

Thirteen ports, one for each key from C to the C above: each plays
its key at once. Green means every note of the melody was played back
in order, and every pair together on the rungs that ask for pairs.

Clocked: the melody plays and the answer is timed whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ByEarEnv(TaskEnv):
    """Deterministic, stepped view of one By Ear run."""

    task_class = ('neural_workshop.ui.byear', 'ByEar')
    ports = 13
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_by_ear_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> ByEarEnv:
    """A production environment: the task's own defaults."""
    return ByEarEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_by_ear_outcome = ByEarEnv.verifier()

__all__ = ['ByEarEnv', 'make_by_ear_env',
           'verify_by_ear_outcome']
