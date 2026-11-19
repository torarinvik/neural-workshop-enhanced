# -*- coding: utf-8 -*-
"""Wait and See.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, unevenwait

LOOK = 1


def deal(rung: int, rng: Optional[random.Random] = None) -> framed.Puzzle:
    return unevenwait.deal('uneven', rung, rng, look=LOOK)
