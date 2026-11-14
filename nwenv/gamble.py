# -*- coding: utf-8 -*-
"""The stepped agent boundary for Gamble.

Nine ports. The first eight pull machines one to eight; a port for a
machine the rung has not put out does nothing. The ninth stops: it walks
away with what is left, and only does anything where a pull costs.

Green means the round did not go bust and its pulls were worth at least
par -- worth, not won: each pull counts what its machine paid on average
at that moment, so luck neither passes nor fails a round. Par is set
from what a discounted Thompson-sampling reference's pulls were worth on
the identical deal; past rung twenty it asks for more than that.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: Pull a machine: ports 0-7. Then this.
STOP = 8


class GambleEnv(TaskEnv):
    """Deterministic, stepped view of one Gamble run."""

    task_class = ('neural_workshop.ui.gamble', 'Gamble')
    ports = 9
    clocked = False
    action = 'steer'
    open_phase = ('pulling',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_gamble_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> GambleEnv:
    """A production environment: the task's own defaults."""
    return GambleEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_gamble_outcome = GambleEnv.verifier()

__all__ = ['GambleEnv', 'STOP', 'make_gamble_env', 'verify_gamble_outcome']
