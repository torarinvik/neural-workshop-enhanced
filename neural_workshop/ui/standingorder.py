# -*- coding: utf-8 -*-
"""Standing Order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import standingorder as model
from .keptrule import SameOrOpposite


class StandingOrder(SameOrOpposite):
    """Standing Order."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Standing Order', 'standing_order', \
        'STANDINGORDER'
    LOOK = model.LOOK

    def _make(self):
        return model.deal(self.rung, rng=self.rng, ledger=self.ledger)
