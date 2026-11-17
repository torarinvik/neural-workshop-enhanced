# -*- coding: utf-8 -*-
"""Top Card on screen: a pile of numbered cards.

For the agent boundary: seven ports: port k names the card numbered k+1.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import topcard as model
from ..i18n import _
from .scenetask import SceneChoice


class TopCard(SceneChoice):
    """Top Card."""

    instance: Optional['TopCard'] = None

    TITLE = 'Top Card'
    TASK_ID = 'top_card'
    PREFIX = 'TOPCARD'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
