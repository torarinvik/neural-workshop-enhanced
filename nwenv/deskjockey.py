# -*- coding: utf-8 -*-
"""The stepped agent boundary for Desk Jockey.

Fifteen ports: 0 approves the form on top of the tray, 1 sends it
back, 2 holds it, 3-5 forward it to Finance, Purchasing and
Personnel, and port 5 + n rejects it under rule n. Ports the book has
no use for do nothing. Green means the tray was cleared with no more
wrong than the rung allows.

Turn-based, so it takes the think clock: the desk stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class DeskJockeyEnv(TaskEnv):
    """Deterministic, stepped view of one Desk Jockey run."""

    task_class = ('neural_workshop.ui.deskjockey', 'DeskJockey')
    ports = 15
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_desk_jockey_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> DeskJockeyEnv:
    """A production environment: the task's own defaults."""
    return DeskJockeyEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_desk_jockey_outcome = DeskJockeyEnv.verifier()

__all__ = ['DeskJockeyEnv', 'make_desk_jockey_env',
           'verify_desk_jockey_outcome']
