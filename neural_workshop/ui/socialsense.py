# -*- coding: utf-8 -*-
"""Social Sense on screen: the text in a box, the answers on buttons.

See :mod:`neural_workshop.socialsense` for what is asked, and
:mod:`neural_workshop.ui.feelings` for the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import socialsense as model
from ..i18n import _
from .feelings import FeelingTask


class SocialSense(FeelingTask):
    """Why do people do it, and what comes of it?"""

    instance: Optional['SocialSense'] = None

    TITLE = 'Social Sense'
    TASK_ID = 'social_sense'
    PREFIX = 'SENSE'
    CATEGORY = 'social'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('Why do people do it, and what comes of it?')
        return ok
