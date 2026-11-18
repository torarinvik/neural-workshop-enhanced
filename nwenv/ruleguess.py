# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Rule?.

Turn-based, so these take the think clock: nothing moves until a port
is pressed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any

from .taskenv import TaskEnv


class _Rung(TaskEnv):
    """What every wrapper here shares."""

    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class WhichRuleEnv(_Rung):
    """Which Rule?: Three ports, one a card, from the left. Every
    press is judged at once."""

    task_class = ('neural_workshop.ui.ruleguess', 'WhichRule')
    ports = 3


verify_which_rule_outcome = WhichRuleEnv.verifier()

__all__ = ['WhichRuleEnv']
