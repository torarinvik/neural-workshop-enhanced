# -*- coding: utf-8 -*-
"""Flash and Beep on screen: a lamp that flashes.

For the agent boundary: four ports: 0 says the flash came first and 1 the beep; where the
flashes are counted, port k answers k+1. The beeps reach the agent
only as sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import flashbeep as model
from ..i18n import _
from .scenetask import SceneShow


class FlashBeep(SceneShow):
    """Flash and Beep."""

    instance: Optional['FlashBeep'] = None

    TITLE = 'Flash and Beep'
    TASK_ID = 'flash_and_beep'
    PREFIX = 'FLASHBEEP'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
