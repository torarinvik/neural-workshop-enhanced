# -*- coding: utf-8 -*-
"""Which Ear on screen: nothing to see: the tones are the task.

For the agent boundary: two ports: 0 says left, 1 right. The tones reach the agent only as
sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import whichear as model
from ..i18n import _
from .scenetask import SceneShow


class WhichEar(SceneShow):
    """Which Ear."""

    instance: Optional['WhichEar'] = None

    TITLE = 'Which Ear'
    TASK_ID = 'which_ear'
    PREFIX = 'WHICHEAR'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
