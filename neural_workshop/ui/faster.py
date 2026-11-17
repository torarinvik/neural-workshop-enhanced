# -*- coding: utf-8 -*-
"""Faster on screen: two windows of moving dots.

For the agent boundary: two ports: 0 says the left window, 1 the right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import faster as model
from ..i18n import _
from .scenetask import SceneShow


class Faster(SceneShow):
    """Faster."""

    instance: Optional['Faster'] = None

    TITLE = 'Faster'
    TASK_ID = 'faster'
    PREFIX = 'FASTER'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
