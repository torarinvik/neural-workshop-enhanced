# -*- coding: utf-8 -*-
"""Far Size on screen: posts on ground running to the horizon.

For the agent boundary: four ports: port k picks post k, from the left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import farsize as model
from ..i18n import _
from .scenetask import SceneChoice


class FarSize(SceneChoice):
    """Far Size."""

    instance: Optional['FarSize'] = None

    TITLE = 'Far Size'
    TASK_ID = 'far_size'
    PREFIX = 'FARSIZE'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
