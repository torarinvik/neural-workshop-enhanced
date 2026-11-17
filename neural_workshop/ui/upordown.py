# -*- coding: utf-8 -*-
"""Up or Down on screen: nothing to see: the tones are the task.

For the agent boundary: three ports: 0 says up and 1 down; with three tones, port k says
tone k was the highest. The tones reach the agent only as sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import upordown as model
from ..i18n import _
from .scenetask import SceneShow


class UpOrDown(SceneShow):
    """Up or Down."""

    instance: Optional['UpOrDown'] = None

    TITLE = 'Up or Down'
    TASK_ID = 'up_or_down'
    PREFIX = 'UPORDOWN'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
