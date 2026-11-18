# -*- coding: utf-8 -*-
"""The stepped agent boundary for Unicycle.

Ten ports: 0 and 1 pedal and back-pedal; 2 and 3 lean back and
forward; 4-7 pedal or back-pedal while leaning back or forward; 8 and 9
lean left and right; each for the step it is sent in. Green means the flag was reached in time
with the rider's head off the ground.

Clocked: the rider falls whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class UnicycleEnv(TaskEnv):
    """Deterministic, stepped view of one Unicycle run."""

    task_class = ('neural_workshop.ui.unicycle', 'Unicycle')
    ports = 10
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_unicycle_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> UnicycleEnv:
    """A production environment: the task's own defaults."""
    return UnicycleEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_unicycle_outcome = UnicycleEnv.verifier()

__all__ = ['UnicycleEnv', 'make_unicycle_env',
           'verify_unicycle_outcome']
