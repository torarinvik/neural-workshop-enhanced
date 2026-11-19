# -*- coding: utf-8 -*-
"""A wait of uneven length, on screen: a place lights, a wait of a
length drawn each trial, and the question.

For the agent boundary: Uneven Wait has four ports, one a square, in
reading order. Any press before the question is put ends the trial
unpaid.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import unevenwait as model
from .keptcue import CueTask


class UnevenTask(CueTask):
    FAMILY = model


class UnevenWait(UnevenTask):
    """A place lights, then a wait of uneven length."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Uneven Wait', 'uneven_wait', 'UNEVENWAIT'
    KIND, LOOK = 'uneven', 0
