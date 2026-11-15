# -*- coding: utf-8 -*-
"""The stepped agent boundary for Who Knows What?.

Four ports, one per container, in the order the room shows them; a port
past the containers the story has does nothing. Green means the answer
was right; there is no par.

Turn-based, so it takes the think clock: the story is all on screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhoKnowsWhatEnv(TaskEnv):
    """Deterministic, stepped view of one Who Knows What? run."""

    task_class = ('neural_workshop.ui.beliefs', 'WhoKnowsWhat')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_who_knows_what_env(seed: int = 0, shm_name: Optional[str] = None
                            ) -> WhoKnowsWhatEnv:
    """A production environment: the task's own defaults."""
    return WhoKnowsWhatEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_who_knows_what_outcome = WhoKnowsWhatEnv.verifier()

__all__ = ['WhoKnowsWhatEnv', 'make_who_knows_what_env',
           'verify_who_knows_what_outcome']
