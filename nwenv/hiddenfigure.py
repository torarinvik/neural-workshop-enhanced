# -*- coding: utf-8 -*-
"""The stepped agent boundary for Hidden Figure.

Four ports: port k picks drawing k, from the left.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HiddenFigureEnv(TaskEnv):
    """Deterministic, stepped view of one Hidden Figure run."""

    task_class = ('neural_workshop.ui.hiddenfigure', 'HiddenFigure')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_hidden_figure_env(seed: int = 0,
                             shm_name: Optional[str] = None) -> HiddenFigureEnv:
    """A production environment: the task's own defaults."""
    return HiddenFigureEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_hidden_figure_outcome = HiddenFigureEnv.verifier()

__all__ = ['HiddenFigureEnv', 'make_hidden_figure_env',
           'verify_hidden_figure_outcome']
