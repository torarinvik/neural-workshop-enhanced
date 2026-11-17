# -*- coding: utf-8 -*-
"""Texture Edge on screen: a page of small strokes with one patch unlike the rest.

For the agent boundary: four ports: 0 says left and 1 right; with four parts, port k picks
part k in reading order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import textureedge as model
from ..i18n import _
from .scenetask import SceneChoice


class TextureEdge(SceneChoice):
    """Texture Edge."""

    instance: Optional['TextureEdge'] = None

    TITLE = 'Texture Edge'
    TASK_ID = 'texture_edge'
    PREFIX = 'TEXEDGE'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
