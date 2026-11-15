# -*- coding: utf-8 -*-
"""The stepped agent boundary for Dam Keeper.

Six ports: 0, 2 and 4 open the gates of dams 1-3 a notch; 1, 3 and 5
shut them a notch (only as many dams as the valley has). Green means
the storms passed with no dam overtopped, no reservoir run dry and the
town never flooded.

Clocked: the rain falls and the rivers run whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class DamKeeperEnv(TaskEnv):
    """Deterministic, stepped view of one Dam Keeper run."""

    task_class = ('neural_workshop.ui.damkeeper', 'DamKeeper')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_dam_keeper_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> DamKeeperEnv:
    """A production environment: the task's own defaults."""
    return DamKeeperEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_dam_keeper_outcome = DamKeeperEnv.verifier()

__all__ = ['DamKeeperEnv', 'make_dam_keeper_env',
           'verify_dam_keeper_outcome']
