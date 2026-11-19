# -*- coding: utf-8 -*-
"""Round Again.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, ownpress

CYCLE = (2, 0, 3, 1)
LOOK = 1


def deal(rung: int, rng: Optional[random.Random] = None,
         ledger: Optional[ownpress.Ledger] = None) -> framed.Puzzle:
    return ownpress.deal('cycle', rung, rng=rng, look=LOOK, ledger=ledger,
                         cycle=CYCLE)
