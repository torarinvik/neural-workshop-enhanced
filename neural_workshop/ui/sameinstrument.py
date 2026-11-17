# -*- coding: utf-8 -*-
"""Same Instrument on screen: nothing to see: the notes are the task.

For the agent boundary: three ports: 0 says the same and 1 different; with three notes, port
k says note k was the odd one. The notes reach the agent only as
sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import sameinstrument as model
from ..i18n import _
from .scenetask import SceneShow


class SameInstrument(SceneShow):
    """Same Instrument."""

    instance: Optional['SameInstrument'] = None

    TITLE = 'Same Instrument'
    TASK_ID = 'same_instrument'
    PREFIX = 'SAMEINSTR'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
