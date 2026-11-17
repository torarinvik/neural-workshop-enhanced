# -*- coding: utf-8 -*-
"""Second Thoughts on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.secondthoughts` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import secondthoughts as model
from ..i18n import _
from .feelings import FeelingTask


class SecondThoughts(FeelingTask):
    """Think twice before answering."""

    instance: Optional['SecondThoughts'] = None

    TITLE = 'Second Thoughts'
    TASK_ID = 'second_thoughts'
    PREFIX = 'SECOND'
    CATEGORY = 'rationality'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('The first answer that comes to mind is not always right')
        return ok
