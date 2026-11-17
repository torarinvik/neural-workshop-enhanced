# -*- coding: utf-8 -*-
"""Steeper on screen: two slopes, framed higher up.

For the agent boundary: two ports: 0 says the left line, 1 the right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import steeper as model
from ..i18n import _
from .scenetask import SceneChoice


class Steeper(SceneChoice):
    """Steeper."""

    instance: Optional['Steeper'] = None

    TITLE = 'Steeper'
    TASK_ID = 'steeper'
    PREFIX = 'STEEPER'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
