# -*- coding: utf-8 -*-
"""The stepped agent boundary for Sokoban Live.

Four ports: 0-3 step the worker up, down, left and right, pushing a
crate in the way. Green means every pad was covered in time without a
guard catching the worker.

Clocked: the guards walk whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SokobanLiveEnv(TaskEnv):
    """Deterministic, stepped view of one Sokoban Live run."""

    task_class = ('neural_workshop.ui.sokobanlive', 'SokobanLive')
    ports = 4
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_sokoban_live_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> SokobanLiveEnv:
    """A production environment: the task's own defaults."""
    return SokobanLiveEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_sokoban_live_outcome = SokobanLiveEnv.verifier()

__all__ = ['SokobanLiveEnv', 'make_sokoban_live_env',
           'verify_sokoban_live_outcome']
