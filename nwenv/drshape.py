# -*- coding: utf-8 -*-
"""The stepped agent boundary for Dr Shape.

Six ports: 0-5 pick card 1-6 (only as many as are shown; a pick
before the turtle finishes does nothing). Green means the pick was the
shape the turtle drew -- or, when the cards are sounds, the sound that
shape makes. Each frame also carries the stereo sound made since the
last one: every stroke is a note, its height the pitch, its left-right
place the pan (sliding as the stroke does), its nearness the loudness.

Clocked: the turtle draws, and the choosing time runs out, whether or not
the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class DrShapeEnv(TaskEnv):
    """Deterministic, stepped view of one Dr Shape run."""

    task_class = ('neural_workshop.ui.drshape', 'DrShape')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_dr_shape_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> DrShapeEnv:
    """A production environment: the task's own defaults."""
    return DrShapeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_dr_shape_outcome = DrShapeEnv.verifier()

__all__ = ['DrShapeEnv', 'make_dr_shape_env',
           'verify_dr_shape_outcome']
