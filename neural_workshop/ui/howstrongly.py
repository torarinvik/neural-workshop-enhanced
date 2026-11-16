# -*- coding: utf-8 -*-
"""How Strongly on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.howstrongly` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import howstrongly as model
from ..i18n import _
from .feelings import FeelingTask


class HowStrongly(FeelingTask):
    """How strongly does the character feel each emotion?"""

    instance: Optional['HowStrongly'] = None

    TITLE = 'How Strongly'
    TASK_ID = 'how_strongly'
    PREFIX = 'STRONG'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('How strongly does the character feel each emotion?')
        return ok
