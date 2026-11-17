# -*- coding: utf-8 -*-
"""Louder on screen: nothing to see: the tones are the task.

For the agent boundary: three ports: port k says tone k was the loudest. The tones reach the
agent only as sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import louder as model
from ..i18n import _
from .scenetask import SceneShow


class Louder(SceneShow):
    """Louder."""

    instance: Optional['Louder'] = None

    TITLE = 'Louder'
    TASK_ID = 'louder'
    PREFIX = 'LOUDER'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
