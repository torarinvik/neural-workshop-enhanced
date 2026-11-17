# -*- coding: utf-8 -*-
"""The stepped agent boundary for Colour Match.

Six ports: port k picks swatch k, from the left.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ColourMatchEnv(TaskEnv):
    """Deterministic, stepped view of one Colour Match run."""

    task_class = ('neural_workshop.ui.colourmatch', 'ColourMatch')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_colour_match_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> ColourMatchEnv:
    """A production environment: the task's own defaults."""
    return ColourMatchEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_colour_match_outcome = ColourMatchEnv.verifier()

__all__ = ['ColourMatchEnv', 'make_colour_match_env',
           'verify_colour_match_outcome']
