# -*- coding: utf-8 -*-
"""The stepped agent boundary for Cricket Hunt.

Seven ports: 0 and 1 walk forward and back, 2 and 3 turn, 4 and 5 look
up and down, each for the step; 6 grabs. Green means every cricket was
caught before the misses ran out.

Clocked: the crickets chirp whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CricketHuntEnv(TaskEnv):
    """Deterministic, stepped view of one Cricket Hunt run."""

    task_class = ('neural_workshop.ui.crickethunt', 'CricketHunt')
    ports = 7
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_cricket_hunt_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> CricketHuntEnv:
    """A production environment: the task's own defaults."""
    return CricketHuntEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_cricket_hunt_outcome = CricketHuntEnv.verifier()

__all__ = ['CricketHuntEnv', 'make_cricket_hunt_env',
           'verify_cricket_hunt_outcome']
