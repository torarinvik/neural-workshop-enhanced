# -*- coding: utf-8 -*-
"""The stepped agent boundary for Explore or Exploit.

Eight ports, one per machine; a port past the machines the run has does
nothing. A trial is one run of pulls; green means it collected at least
par, from a fading-average explorer on the identical run.

Turn-based, so it takes the think clock: nothing happens between pulls.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ExploreOrExploitEnv(TaskEnv):
    """Deterministic, stepped view of one Explore or Exploit run."""

    task_class = ('neural_workshop.ui.bandit', 'ExploreOrExploit')
    ports = 8
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_explore_exploit_env(seed: int = 0, shm_name: Optional[str] = None
                             ) -> ExploreOrExploitEnv:
    """A production environment: the task's own defaults."""
    return ExploreOrExploitEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_explore_exploit_outcome = ExploreOrExploitEnv.verifier()

__all__ = ['ExploreOrExploitEnv', 'make_explore_exploit_env',
           'verify_explore_exploit_outcome']
