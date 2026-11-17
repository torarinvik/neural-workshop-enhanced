# -*- coding: utf-8 -*-
"""Gaze on screen: a face and numbered things around it.

For the agent boundary: eight ports: port k picks thing k+1.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import gaze as model
from ..i18n import _
from .scenetask import SceneChoice


class Gaze(SceneChoice):
    """Gaze."""

    instance: Optional['Gaze'] = None

    TITLE = 'Gaze'
    TASK_ID = 'gaze'
    PREFIX = 'GAZE'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
