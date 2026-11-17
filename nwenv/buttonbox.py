# -*- coding: utf-8 -*-
"""The stepped agent boundary for Button Box.

Thirteen ports: 0-11 press buttons 1-12 (those beyond the trial's
buttons do nothing); 12 resets the figure, free. Green means the
figure matched the target before the presses ran out.

Turn-based, so it takes the think clock: nothing moves until a button is pressed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ButtonBoxEnv(TaskEnv):
    """Deterministic, stepped view of one Button Box run."""

    task_class = ('neural_workshop.ui.buttonbox', 'ButtonBox')
    ports = 13
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_button_box_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> ButtonBoxEnv:
    """A production environment: the task's own defaults."""
    return ButtonBoxEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_button_box_outcome = ButtonBoxEnv.verifier()

__all__ = ['ButtonBoxEnv', 'make_button_box_env',
           'verify_button_box_outcome']
