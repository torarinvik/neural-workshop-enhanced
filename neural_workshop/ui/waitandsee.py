# -*- coding: utf-8 -*-
"""Wait and See.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .. import waitandsee as model
from .unevenwait import UnevenWait


class WaitAndSee(UnevenWait):
    """Wait and See."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Wait and See', 'wait_and_see', 'WAITANDSEE'
    LOOK = model.LOOK

    def _make(self):
        return model.deal(self.rung, rng=self.rng)
