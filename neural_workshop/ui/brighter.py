# -*- coding: utf-8 -*-
"""Brighter on screen: grey patches on their grounds.

For the agent boundary: four ports: port k picks patch k, from the left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import brighter as model
from ..i18n import _
from .scenetask import SceneChoice


class Brighter(SceneChoice):
    """Brighter."""

    instance: Optional['Brighter'] = None

    TITLE = 'Brighter'
    TASK_ID = 'brighter'
    PREFIX = 'BRIGHTER'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
