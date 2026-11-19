# -*- coding: utf-8 -*-
"""Busy Beads.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import busybeads as model
from .handsoff import BusyWait


class BusyBeads(BusyWait):
    """Busy Beads."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Busy Beads', 'busy_beads', 'BUSYBEADS'
    LOOK = model.LOOK

    def _make(self):
        return model.deal(self.rung, rng=self.rng)
