# -*- coding: utf-8 -*-
"""Several kept, one asked for, on screen: places light one after
another in colours of their own, a wait, then the question with the
colour wanted beside the question mark.

For the agent boundary: Which Was Where? has four ports, one a square,
in reading order. Any press before the question is put ends the trial
unpaid.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import severalcues as model
from .keptcue import CueTask


class SeveralTask(CueTask):
    FAMILY = model


class WhichWasWhere(SeveralTask):
    """Places light in colours of their own: where was this one?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Which Was Where?', 'which_was_where', \
        'WHICHWASWHERE'
    KIND, LOOK = 'several', 0
