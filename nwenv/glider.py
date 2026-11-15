# -*- coding: utf-8 -*-
"""The stepped agent boundary for Glider.

One port: 0 lifts for the step it is sent in; send it every step to
keep climbing. Green means the glider passed every wall without
touching rock, roof or floor.

Clocked: the glider flies on whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class GliderEnv(TaskEnv):
    """Deterministic, stepped view of one Glider run."""

    task_class = ('neural_workshop.ui.glider', 'Glider')
    ports = 1
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_glider_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> GliderEnv:
    """A production environment: the task's own defaults."""
    return GliderEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_glider_outcome = GliderEnv.verifier()

__all__ = ['GliderEnv', 'make_glider_env',
           'verify_glider_outcome']
