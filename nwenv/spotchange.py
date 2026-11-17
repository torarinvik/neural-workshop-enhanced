# -*- coding: utf-8 -*-
"""The stepped agent boundary for Spot the Change.

Sixteen ports: port k picks part k of the picture, in reading order.

Clocked: the pictures flicker and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SpotChangeEnv(TaskEnv):
    """Deterministic, stepped view of one Spot the Change run."""

    task_class = ('neural_workshop.ui.spotchange', 'SpotChange')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_spot_the_change_env(seed: int = 0,
                               shm_name: Optional[str] = None) -> SpotChangeEnv:
    """A production environment: the task's own defaults."""
    return SpotChangeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_spot_the_change_outcome = SpotChangeEnv.verifier()

__all__ = ['SpotChangeEnv', 'make_spot_the_change_env',
           'verify_spot_the_change_outcome']
