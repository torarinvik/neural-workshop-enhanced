# -*- coding: utf-8 -*-
"""Standing Order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, keptrule

LOOK = 1


def deal(rung: int, rng: Optional[random.Random] = None,
         ledger: Optional[keptrule.Ledger] = None) -> framed.Puzzle:
    return keptrule.deal('rule', rung, rng, look=LOOK, ledger=ledger)
