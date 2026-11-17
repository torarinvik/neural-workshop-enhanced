# -*- coding: utf-8 -*-
"""Bad Argument on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.badargument` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import badargument as model
from ..i18n import _
from .feelings import FeelingTask


class BadArgument(FeelingTask):
    """Does the conclusion follow?"""

    instance: Optional['BadArgument'] = None

    TITLE = 'Bad Argument'
    TASK_ID = 'bad_argument'
    PREFIX = 'ARGUE'
    CATEGORY = 'rationality'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('Does the conclusion follow from what is given?')
        return ok
