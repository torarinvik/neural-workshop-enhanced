# -*- coding: utf-8 -*-
"""The stepped agent boundary for Sonar.

Six ports: four steer a cursor round the grid and cost nothing, one
pings the cell under it and one digs there. Steered rather than a port
per cell because the grid runs to twenty-four a side, and five hundred
and seventy-six ports would be a decoder problem rather than a
decision one.

Green means the target was found for no more than par: what a Bayesian
reference player paid on the identical deal -- the same noise on the
same numbered action, the same drift after it -- plus the rung's slack,
which past rung twenty is negative.

Turn-based, so it takes the think clock, and on this task that prices
deliberation against a target that may be drifting anyway.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: Cursor up, down, left, right; then ping; then dig.
PING, DIG = 4, 5


class SonarEnv(TaskEnv):
    """Deterministic, stepped view of one Sonar run."""

    task_class = ('neural_workshop.ui.sonar', 'Sonar')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('searching',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_sonar_env(seed: int = 0,
                   shm_name: Optional[str] = None) -> SonarEnv:
    """A production environment: the task's own defaults."""
    return SonarEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_sonar_outcome = SonarEnv.verifier()

__all__ = ['DIG', 'PING', 'SonarEnv', 'make_sonar_env',
           'verify_sonar_outcome']
