# -*- coding: utf-8 -*-
"""Roll Call.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import rollcall as model
from .severalcues import WhichWasWhere


class RollCall(WhichWasWhere):
    """Roll Call."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Roll Call', 'roll_call', 'ROLLCALL'
    LOOK = model.LOOK

    def _make(self):
        return model.deal(self.rung, rng=self.rng)
