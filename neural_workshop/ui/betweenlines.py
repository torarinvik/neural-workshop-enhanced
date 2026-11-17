# -*- coding: utf-8 -*-
"""Between the Lines on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.betweenlines` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import betweenlines as model
from ..i18n import _
from .feelings import FeelingTask


class BetweenTheLines(FeelingTask):
    """What do they really mean?"""

    instance: Optional['BetweenTheLines'] = None

    TITLE = 'Between the Lines'
    TASK_ID = 'between_the_lines'
    PREFIX = 'LINES'
    CATEGORY = 'social'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('What do they really mean?')
        return ok
