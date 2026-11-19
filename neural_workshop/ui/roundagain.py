# -*- coding: utf-8 -*-
"""Round Again.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import roundagain as model
from .ownpress import OwnPressTask


class RoundAgain(OwnPressTask):
    """Round Again."""

    instance = None
    TITLE = 'Round Again'
    TASK_ID = 'round_again'
    PREFIX = 'ROUNDAGAIN'
    KIND = 'cycle'
    LOOK = model.LOOK

    def _make(self):
        return model.deal(self.rung, rng=self.rng, ledger=self.ledger)
