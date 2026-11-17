# -*- coding: utf-8 -*-
"""The stepped agent boundary for How Many Beeps.

Nine ports: port k answers k+1 beeps. The beeps reach the agent only
as sound.

Clocked: the sounds play and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HowManyBeepsEnv(TaskEnv):
    """Deterministic, stepped view of one How Many Beeps run."""

    task_class = ('neural_workshop.ui.howmanybeeps', 'HowManyBeeps')
    ports = 9
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_how_many_beeps_env(seed: int = 0,
                              shm_name: Optional[str] = None) -> HowManyBeepsEnv:
    """A production environment: the task's own defaults."""
    return HowManyBeepsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_how_many_beeps_outcome = HowManyBeepsEnv.verifier()

__all__ = ['HowManyBeepsEnv', 'make_how_many_beeps_env',
           'verify_how_many_beeps_outcome']
