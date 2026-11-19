# -*- coding: utf-8 -*-
"""Odd Stripe.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import twins
from .i18n import _


def deal(rung: int, rng: Optional[random.Random] = None) -> twins.Puzzle:
    rng = rng or random.Random()
    n = twins.size('odd', rung)
    odd = rng.randrange(n)
    base = rng.randrange(4)
    other = rng.choice([k for k in range(4) if k != base])
    data = {'items': [other if k == odd else base for k in range(n)],
            'hue': rng.randrange(len(twins.HUES_B)),
            'turn': rng.random()}
    answer = n - 1 - odd
    return twins.Puzzle('odd', 'b', tuple(str(k + 1) for k in range(n)),
                        answer, data, _('Which one is the odd one out?'))
