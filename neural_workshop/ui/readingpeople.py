# -*- coding: utf-8 -*-
"""Reading People on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.readingpeople` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import readingpeople as model
from ..i18n import _
from .feelings import FeelingTask


class ReadingPeople(FeelingTask):
    """Read the story: how do they feel, why, what helps?"""

    instance: Optional['ReadingPeople'] = None

    TITLE = 'Reading People'
    TASK_ID = 'reading_people'
    PREFIX = 'READ'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('Read the story: how do they feel, why, what helps?')
        return ok
