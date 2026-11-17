# -*- coding: utf-8 -*-
"""What Share on screen: a bar, a round or a scatter, part coloured.

For the agent boundary: six ports: port k picks answer k (the shares rise from the left).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import whatshare as model
from ..i18n import _
from .scenetask import SceneChoice


class WhatShare(SceneChoice):
    """What Share."""

    instance: Optional['WhatShare'] = None

    TITLE = 'What Share'
    TASK_ID = 'what_share'
    PREFIX = 'WHATSHARE'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
