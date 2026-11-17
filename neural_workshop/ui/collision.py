# -*- coding: utf-8 -*-
"""Collision Course on screen: two balls rolling toward a crossing.

For the agent boundary: two ports: 0 says they will hit, 1 that they will miss.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import collision as model
from ..i18n import _
from .scenetask import SceneShow


class Collision(SceneShow):
    """Collision Course."""

    instance: Optional['Collision'] = None

    TITLE = 'Collision Course'
    TASK_ID = 'collision_course'
    PREFIX = 'COLLISION'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
