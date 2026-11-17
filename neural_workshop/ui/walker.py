# -*- coding: utf-8 -*-
"""Walker on screen: eleven lights on a walking figure.

For the agent boundary: two ports: 0 says the figure faces left, 1 right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import walker as model
from ..i18n import _
from .scenetask import SceneShow


class Walker(SceneShow):
    """Walker."""

    instance: Optional['Walker'] = None

    TITLE = 'Walker'
    TASK_ID = 'walker'
    PREFIX = 'WALKER'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
