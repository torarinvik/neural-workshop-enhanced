# -*- coding: utf-8 -*-
"""Why They Feel on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.whytheyfeel` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import whytheyfeel as model
from ..i18n import _
from .feelings import FeelingTask


class WhyTheyFeel(FeelingTask):
    """What would anyone feel, in their place?"""

    instance: Optional['WhyTheyFeel'] = None

    TITLE = 'Why They Feel'
    TASK_ID = 'why_they_feel'
    PREFIX = 'WHY'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('What would anyone feel, in their place?')
        return ok
