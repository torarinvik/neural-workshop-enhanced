# -*- coding: utf-8 -*-
"""Which Way on screen: a field of short-lived dots.

For the agent boundary: eight ports: 0 left, 1 right, 2 up, 3 down, 4 up left, 5 up right,
6 down left, 7 down right (only as many as the rung asks).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import whichway as model
from ..i18n import _
from .scenetask import SceneShow


class WhichWay(SceneShow):
    """Which Way."""

    instance: Optional['WhichWay'] = None

    TITLE = 'Which Way'
    TASK_ID = 'which_way'
    PREFIX = 'WHICHWAY'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
