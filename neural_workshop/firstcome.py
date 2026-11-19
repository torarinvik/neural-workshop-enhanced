# -*- coding: utf-8 -*-
"""First Come.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, newestfirst

LOOK = 1


def deal(rung: int, rng: Optional[random.Random] = None) -> framed.Puzzle:
    return newestfirst.deal('first', rung, rng, look=LOOK)
