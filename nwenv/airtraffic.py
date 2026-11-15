# -*- coding: utf-8 -*-
"""The stepped agent boundary for Air Traffic.

Twelve ports: 0-7 pick the plane in that slot; 8 hold, 9 turn left,
10 turn right, 11 clear to land -- each for the picked plane. Green
means every plane landed with nothing lost: no two planes inside the
separation minimum, none in a storm, out of fuel or out of the
airspace.

Clocked: the trains run whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class AirTrafficEnv(TaskEnv):
    """Deterministic, stepped view of one Air Traffic run."""

    task_class = ('neural_workshop.ui.airtraffic', 'AirTraffic')
    ports = 12
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_air_traffic_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> AirTrafficEnv:
    """A production environment: the task's own defaults."""
    return AirTrafficEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_air_traffic_outcome = AirTrafficEnv.verifier()

__all__ = ['AirTrafficEnv', 'make_air_traffic_env', 'verify_air_traffic_outcome']
