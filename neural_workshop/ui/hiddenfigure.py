# -*- coding: utf-8 -*-
"""Hidden Figure on screen: a small figure and the drawings that may hide it.

For the agent boundary: four ports: port k picks drawing k, from the left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import hiddenfigure as model
from ..i18n import _
from .scenetask import SceneChoice


class HiddenFigure(SceneChoice):
    """Hidden Figure."""

    instance: Optional['HiddenFigure'] = None

    TITLE = 'Hidden Figure'
    TASK_ID = 'hidden_figure'
    PREFIX = 'HIDDENFIG'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
