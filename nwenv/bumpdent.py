# -*- coding: utf-8 -*-
"""The stepped agent boundary for Bump or Dent.

Ten ports: 0 says bump and 1 dent; where the question is how many
are bumps, port k answers k.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BumpDentEnv(TaskEnv):
    """Deterministic, stepped view of one Bump or Dent run."""

    task_class = ('neural_workshop.ui.bumpdent', 'BumpDent')
    ports = 10
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_bump_or_dent_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> BumpDentEnv:
    """A production environment: the task's own defaults."""
    return BumpDentEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_bump_or_dent_outcome = BumpDentEnv.verifier()

__all__ = ['BumpDentEnv', 'make_bump_or_dent_env',
           'verify_bump_or_dent_outcome']
