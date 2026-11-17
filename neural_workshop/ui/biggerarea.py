# -*- coding: utf-8 -*-
"""Bigger Area on screen: filled outlines.

For the agent boundary: four ports: port k picks shape k, from the left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import biggerarea as model
from ..i18n import _
from .scenetask import SceneChoice


class BiggerArea(SceneChoice):
    """Bigger Area."""

    instance: Optional['BiggerArea'] = None

    TITLE = 'Bigger Area'
    TASK_ID = 'bigger_area'
    PREFIX = 'BIGGERAREA'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
