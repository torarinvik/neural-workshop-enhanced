# -*- coding: utf-8 -*-
"""Lever and Latch.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import twostage
from .longwalk import Puzzle

ORDER = (2, 3, 0, 1)
COLOURS = ((246, 238, 228), (120, 60, 50), (200, 90, 40), (40, 120, 90))


def deal(rung: int, rng: Optional[random.Random] = None) -> Puzzle:
    return twostage.deal('plate', rung, rng, order=ORDER, look=0)
