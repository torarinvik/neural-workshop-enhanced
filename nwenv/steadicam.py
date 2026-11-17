# -*- coding: utf-8 -*-
"""The stepped agent boundary for Steadicam.

Six ports: pan left and right, tilt up and down, zoom in and out, each
for the step it is sent in. Green means the subject was kept in the
framing box for enough of the take.

Clocked: the subject moves whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SteadicamEnv(TaskEnv):
    """Deterministic, stepped view of one Steadicam run."""

    task_class = ('neural_workshop.ui.steadicam', 'Steadicam')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_steadicam_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> SteadicamEnv:
    """A production environment: the task's own defaults."""
    return SteadicamEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_steadicam_outcome = SteadicamEnv.verifier()

__all__ = ['SteadicamEnv', 'make_steadicam_env',
           'verify_steadicam_outcome']
