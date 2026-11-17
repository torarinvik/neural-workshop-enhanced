# -*- coding: utf-8 -*-
"""Colour Match on screen: a sample and a row of swatches.

For the agent boundary: six ports: port k picks swatch k, from the left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import colourmatch as model
from ..i18n import _
from .scenetask import SceneChoice


class ColourMatch(SceneChoice):
    """Colour Match."""

    instance: Optional['ColourMatch'] = None

    TITLE = 'Colour Match'
    TASK_ID = 'colour_match'
    PREFIX = 'COLOURMATCH'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
