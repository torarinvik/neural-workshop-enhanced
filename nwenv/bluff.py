# -*- coding: utf-8 -*-
"""The stepped agent boundary for Bluff.

Two ports: check or fold, and bet or call -- which of each depends on
whether a bet is being faced. The opponent acts by itself in between.
Two ports is all the game needs; what it asks for is in the reading of
the hands that came before, which the log on the right of the screen
shows: both cards where a showdown turned them over, and what each
player did.

Green means the round's choices were worth at least par: worth, not won
-- each hand counts what its choices win on average over every card the
opponent could have held, against what it really does -- set from a
reference that models the opponent from its showdowns, on the identical
deal; past rung twenty it asks for more than that.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

PASSIVE, AGGRESSIVE = 0, 1


class BluffEnv(TaskEnv):
    """Deterministic, stepped view of one Bluff run."""

    task_class = ('neural_workshop.ui.bluff', 'Bluff')
    ports = 2
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_bluff_env(seed: int = 0,
                   shm_name: Optional[str] = None) -> BluffEnv:
    """A production environment: the task's own defaults."""
    return BluffEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_bluff_outcome = BluffEnv.verifier()

__all__ = ['AGGRESSIVE', 'BluffEnv', 'PASSIVE', 'make_bluff_env',
           'verify_bluff_outcome']
