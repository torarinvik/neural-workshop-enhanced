# -*- coding: utf-8 -*-
"""Roll Call.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, severalcues

LOOK = 1


def deal(rung: int, rng: Optional[random.Random] = None) -> framed.Puzzle:
    return severalcues.deal('several', rung, rng, look=LOOK)
