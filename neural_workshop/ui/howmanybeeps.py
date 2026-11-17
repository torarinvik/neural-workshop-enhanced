# -*- coding: utf-8 -*-
"""How Many Beeps on screen: nothing to see: the beeps are the task.

For the agent boundary: nine ports: port k answers k+1 beeps. The beeps reach the agent only
as sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import howmanybeeps as model
from ..i18n import _
from .scenetask import SceneShow


class HowManyBeeps(SceneShow):
    """How Many Beeps."""

    instance: Optional['HowManyBeeps'] = None

    TITLE = 'How Many Beeps'
    TASK_ID = 'how_many_beeps'
    PREFIX = 'BEEPS'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
