# -*- coding: utf-8 -*-
"""Lever and Latch.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import leverlatch as model
from .ministeps import ARROWS, DARK_GROUND
from .twostage import PlateAndGate


class LeverAndLatch(PlateAndGate):
    """Lever and Latch."""

    instance: Optional['LeverAndLatch'] = None
    TITLE = 'Lever and Latch'
    TASK_ID = 'lever_and_latch'
    PREFIX = 'LEVERANDLATCH'

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _colours(self):
        ground, wall, mover, goal = model.COLOURS
        if self.dark:
            ground = DARK_GROUND
            wall = tuple(min(255, c + 110) for c in wall)
        return ground, wall, mover, goal

    def _key(self, symbol: int, modifiers: int) -> None:
        if self.puzzle is not None and symbol in ARROWS:
            self.steer(model.ORDER.index(ARROWS[symbol]))
