# -*- coding: utf-8 -*-
"""The stepped agent boundary for Morning Round.

Six ports. Ports 0 and 1 steer left and right, 2 and 3 pedal faster and
slower, each for the step it is sent in; 4 throws a paper to the left
and 5 to the right. A subscriber thanks you with a chime, a house that
wanted no paper shouts, and a subscriber passed without one sounds a
horn: these are all there is to go by when the rule changes unseen.

Clocked: the clock runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class MorningRoundEnv(TaskEnv):
    """Deterministic, stepped view of one Morning Round run."""

    task_class = ('neural_workshop.ui.morninground', 'MorningRound')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_morning_round_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> MorningRoundEnv:
    """A production environment: the task's own defaults."""
    return MorningRoundEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_morning_round_outcome = MorningRoundEnv.verifier()

__all__ = ['MorningRoundEnv', 'make_morning_round_env',
           'verify_morning_round_outcome']
