# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Urn?.

Two ports: 0 says the left kind of urn, 1 the right. Green means the
kind more likely given the draw (the posterior), not the urn picked.

Turn-based, so it takes the think clock: the urns stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class UrnsEnv(TaskEnv):
    """Deterministic, stepped view of one Which Urn? run."""

    task_class = ('neural_workshop.ui.urns', 'Urns')
    ports = 2
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_which_urn_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> UrnsEnv:
    """A production environment: the task's own defaults."""
    return UrnsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_which_urn_outcome = UrnsEnv.verifier()

__all__ = ['UrnsEnv', 'make_which_urn_env',
           'verify_which_urn_outcome']
