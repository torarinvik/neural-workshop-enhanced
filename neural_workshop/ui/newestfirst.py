# -*- coding: utf-8 -*-
"""The newest counts, or the first counts, on screen: a place lights,
maybe others after it, then the question.

For the agent boundary: The Newest Counts and The First Counts have
four ports, one a square, in reading order. Any press before the
question is put ends the trial unpaid.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import newestfirst as model
from .keptcue import CueTask


class NewestFirstTask(CueTask):
    FAMILY = model


class TheNewestCounts(NewestFirstTask):
    """Places light one after another: where was the last?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'The Newest Counts', 'newest_counts', \
        'NEWESTCOUNTS'
    KIND, LOOK = 'newest', 0


class TheFirstCounts(NewestFirstTask):
    """Places light one after another: where was the first?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'The First Counts', 'first_counts', \
        'FIRSTCOUNTS'
    KIND, LOOK = 'first', 0
