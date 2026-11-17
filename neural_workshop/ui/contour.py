# -*- coding: utf-8 -*-
"""Contour on screen: a field of strokes with a path in it.

For the agent boundary: four ports: 0 says left and 1 right; with four parts, port k picks
part k in reading order (top left, top right, bottom left, bottom
right).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import contour as model
from ..i18n import _
from .scenetask import SceneChoice


class Contour(SceneChoice):
    """Contour."""

    instance: Optional['Contour'] = None

    TITLE = 'Contour'
    TASK_ID = 'contour'
    PREFIX = 'CONTOUR'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
