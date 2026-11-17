# -*- coding: utf-8 -*-
"""Reflection on screen: a figure, a mirror and the candidates.

For the agent boundary: four ports: port k picks figure k (reading order on the right).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import reflection as model
from ..i18n import _
from .scenetask import SceneChoice


class Reflection(SceneChoice):
    """Reflection."""

    instance: Optional['Reflection'] = None

    TITLE = 'Reflection'
    TASK_ID = 'reflection'
    PREFIX = 'REFLECTION'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
