# -*- coding: utf-8 -*-
"""The stepped agent boundary for Rail Yard.

Seventeen ports: 0-14 throw the points numbered 1-15 (only as many as
the yard has), 15 and 16 turn the two tunnel signals between red and
green. Green means every train reached its own station with no
collision and no derailment (one wrong station forgiven below rung 10).

Clocked: the trains run whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class RailYardEnv(TaskEnv):
    """Deterministic, stepped view of one Rail Yard run."""

    task_class = ('neural_workshop.ui.railyard', 'RailYard')
    ports = 17
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_rail_yard_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> RailYardEnv:
    """A production environment: the task's own defaults."""
    return RailYardEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_rail_yard_outcome = RailYardEnv.verifier()

__all__ = ['RailYardEnv', 'make_rail_yard_env', 'verify_rail_yard_outcome']
