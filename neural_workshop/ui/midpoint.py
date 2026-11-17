# -*- coding: utf-8 -*-
"""Midpoint on screen: a line and the marks across it.

For the agent boundary: five ports: port k picks mark k, counted along the line.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import midpoint as model
from ..i18n import _
from .scenetask import SceneChoice


class Midpoint(SceneChoice):
    """Midpoint."""

    instance: Optional['Midpoint'] = None

    TITLE = 'Midpoint'
    TASK_ID = 'midpoint'
    PREFIX = 'MIDPOINT'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
