# -*- coding: utf-8 -*-
"""Number Line on screen: a line with a number at each end.

For the agent boundary: six ports: port k picks answer k (the numbers rise from the left),
or mark k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import numberline as model
from ..i18n import _
from .scenetask import SceneChoice


class NumberLine(SceneChoice):
    """Number Line."""

    instance: Optional['NumberLine'] = None

    TITLE = 'Number Line'
    TASK_ID = 'number_line'
    PREFIX = 'NUMBERLINE'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
