# -*- coding: utf-8 -*-
"""Longer Line on screen: lines, their fins and rails.

For the agent boundary: four ports: port k picks line k (left to right; between rails, port 0
is the lower line).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import longerline as model
from ..i18n import _
from .scenetask import SceneChoice


class LongerLine(SceneChoice):
    """Longer Line."""

    instance: Optional['LongerLine'] = None

    TITLE = 'Longer Line'
    TASK_ID = 'longer_line'
    PREFIX = 'LONGERLINE'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
