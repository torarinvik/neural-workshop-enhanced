# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Is Nearer?.

Six ports, one per solid, counted left to right across the page at the
middle of a sway; a port past the solids the scene holds does nothing.
Up to rung 19 one port answers; from 20 the solids are chosen in turn,
nearest first, and the first wrong one ends the trial. Green means
right; there is no par.

Clocked: from rung 16 the only cue to depth is motion parallax as the
eye sways, so the scene must be watched over time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhichIsNearerEnv(TaskEnv):
    """Deterministic, stepped view of one Which Is Nearer? run."""

    task_class = ('neural_workshop.ui.nearer', 'WhichIsNearer')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_which_is_nearer_env(seed: int = 0, shm_name: Optional[str] = None
                             ) -> WhichIsNearerEnv:
    """A production environment: the task's own defaults."""
    return WhichIsNearerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_which_is_nearer_outcome = WhichIsNearerEnv.verifier()

__all__ = ['WhichIsNearerEnv', 'make_which_is_nearer_env',
           'verify_which_is_nearer_outcome']
