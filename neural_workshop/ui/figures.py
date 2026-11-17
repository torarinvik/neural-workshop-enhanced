# -*- coding: utf-8 -*-
"""Figures of Speech on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.figures` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import figures as model
from ..i18n import _
from .feelings import FeelingTask


class FiguresOfSpeech(FeelingTask):
    """What do the words mean, past what they say?"""

    instance: Optional['FiguresOfSpeech'] = None

    TITLE = 'Figures of Speech'
    TASK_ID = 'figures_of_speech'
    PREFIX = 'FIGURE'
    CATEGORY = 'reasoning'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('What do the words mean, past what they say?')
        return ok
