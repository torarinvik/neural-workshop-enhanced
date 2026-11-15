# -*- coding: utf-8 -*-
"""The stepped agent boundary for Where Was It?.

Thirty-one ports. Port 30 goes on to the next room while studying (and
to the test after the last). Ports 0-29 click a square of the floor in
the test, counted across each row from the front left corner as the
room was first shown, then row by row away from it; a click on a thing
is a click on the square it stands on, and a square past the floor does
nothing. Green means the square was one the question asked for; there
is no par.

Turn-based, so it takes the think clock: each room stays up until the
agent moves on.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

NEXT = 30


class WhereWasItEnv(TaskEnv):
    """Deterministic, stepped view of one Where Was It? run."""

    task_class = ('neural_workshop.ui.rooms', 'WhereWasIt')
    ports = 31
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_where_was_it_env(seed: int = 0, shm_name: Optional[str] = None
                          ) -> WhereWasItEnv:
    """A production environment: the task's own defaults."""
    return WhereWasItEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_where_was_it_outcome = WhereWasItEnv.verifier()

__all__ = ['NEXT', 'WhereWasItEnv', 'make_where_was_it_env',
           'verify_where_was_it_outcome']
