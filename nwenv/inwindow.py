# -*- coding: utf-8 -*-
"""The stepped agent boundary for In the Window.

Clocked: the frames go by, and the time to answer runs, whether or not
the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any

from .taskenv import TaskEnv


class _Rung(TaskEnv):
    """What every wrapper here shares."""

    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class InTheWindowEnv(_Rung):
    """In the Window: Two ports: 0 presses, 1 waits. Green means the
    press came with the marker inside the window."""

    task_class = ('neural_workshop.ui.inwindow', 'InTheWindow')
    ports = 2


verify_in_the_window_outcome = InTheWindowEnv.verifier()

__all__ = ['InTheWindowEnv']
