# -*- coding: utf-8 -*-
"""Which Feeling on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.whichfeeling` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import whichfeeling as model
from ..i18n import _
from .feelings import FeelingTask


class WhichFeeling(FeelingTask):
    """What does the writer of this comment feel?"""

    instance: Optional['WhichFeeling'] = None

    TITLE = 'Which Feeling'
    TASK_ID = 'which_feeling'
    PREFIX = 'FEEL'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('What does the writer of this comment feel?')
        return ok
