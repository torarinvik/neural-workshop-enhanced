# -*- coding: utf-8 -*-
"""Hands off, on screen: a place lights, a wait, and the question.

For the agent boundary: Hands Off and Busy Wait have four ports, one a
square, in reading order. On Hands Off any press before the question
is put ends the trial unpaid; on Busy Wait the wait's jobs must be
pressed, each once, and any other press before the question ends the
trial unpaid.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import handsoff as model
from ..i18n import _
from .keptcue import CueTask


class HandsOffTask(CueTask):
    FAMILY = model


class HandsOff(HandsOffTask):
    """A place lights, then a wait to keep your hands off through."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Hands Off', 'hands_off', 'HANDSOFF'
    KIND, LOOK = 'still', 0


class BusyWait(HandsOffTask):
    """A place lights, then a wait filled with small jobs."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Busy Wait', 'busy_wait', 'BUSYWAIT'
    KIND, LOOK = 'busy', 0
    FOOTNOTE = _('watch; while you wait press the place where a dot '
                 'shows, once each; at the question mark press the '
                 'place that lit   Esc: menu')
