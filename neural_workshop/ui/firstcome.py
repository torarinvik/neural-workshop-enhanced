# -*- coding: utf-8 -*-
"""First Come.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import firstcome as model
from .newestfirst import TheFirstCounts


class FirstCome(TheFirstCounts):
    """First Come."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'First Come', 'first_come', 'FIRSTCOME'
    LOOK = model.LOOK

    def _make(self):
        return model.deal(self.rung, rng=self.rng)
