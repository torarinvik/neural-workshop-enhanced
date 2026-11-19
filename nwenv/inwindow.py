# -*- coding: utf-8 -*-
"""In the Window.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any

from .taskenv import TaskEnv


class _Rung(TaskEnv):
    """In the Window."""

    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class InTheWindowEnv(_Rung):
    """In the Window."""

    task_class = ('neural_workshop.ui.inwindow', 'InTheWindow')
    ports = 2


verify_in_the_window_outcome = InTheWindowEnv.verifier()

__all__ = ['InTheWindowEnv']
