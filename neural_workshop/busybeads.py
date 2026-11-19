# -*- coding: utf-8 -*-
"""Busy Beads.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, handsoff

LOOK = 1


def deal(rung: int, rng: Optional[random.Random] = None) -> framed.Puzzle:
    return handsoff.deal('busy', rung, rng, look=LOOK)
