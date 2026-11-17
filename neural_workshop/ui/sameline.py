# -*- coding: utf-8 -*-
"""Same Line? on screen: lines crossing from left to right.

For the agent boundary: six ports: 0 says yes and 1 no; where the question is which end,
port k picks end k, counted from the top.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import sameline as model
from ..i18n import _
from .scenetask import SceneChoice


class SameLine(SceneChoice):
    """Same Line?."""

    instance: Optional['SameLine'] = None

    TITLE = 'Same Line?'
    TASK_ID = 'same_line'
    PREFIX = 'SAMELINE'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
