# -*- coding: utf-8 -*-
"""Parallel?: are the two lines parallel?

Two long lines. Parallel, or not quite? From rung 4 they lie at any
angle; from rung 7 short hatches cross them, slanted one way on one
line and the other way on the other, which makes parallel lines look
tilted (Zoellner) -- and lines that are not, look parallel.

The ladder:

* rungs 1-3: level lines; eight degrees off, or parallel;
* rungs 4-6: any angle; four degrees;
* rungs 7-9: hatching; two and a half;
* rungs 10-12: a degree and a half;
* from rung 13: narrowing toward a quarter of a degree.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

YES, NO = 0, 1


class Grade(NamedTuple):
    rung: int
    off: float           # degrees, when they are not
    angles: bool
    hatched: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        off=(8.0 if r < 4 else 4.0 if r < 7 else 2.5 if r < 10
             else 1.5 if r < 13 else max(0.25, 1.2 * 0.88 ** (r - 13))),
        angles=r >= 4,
        hatched=r >= 7)


class Puzzle(NamedTuple):
    level: Grade
    angle: float         # the first line's, degrees
    tilt: float          # the second's, relative to the first
    gap: float
    hatch: int           # which way the first line's hatches slant
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    return YES if p.tilt == 0 else NO


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, 2)
    sign = draw.choice((-1, 1))
    tilt = 0.0 if answer == YES else level.off * sign
    # Hatches slanted to hide a real tilt, or to fake one.
    hatch = sign if answer == NO else draw.choice((-1, 1))
    return Puzzle(level, draw.uniform(0, 180) if level.angles else 0.0, tilt,
                  draw.uniform(0.16, 0.24), hatch, draw.random(),
                  draw.choice(S.PAPERS), _('Are the two lines parallel?'),
                  (_('Yes'), _('No')), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    ink = S.hsv(p.hue, 0.6, 0.4)
    out = []
    cx, cy = S.W / 2, 0.5
    base = math.radians(p.angle)
    nx, ny = -math.sin(base), math.cos(base)
    half = 0.4
    for k, extra in ((0, 0.0), (1, p.tilt)):
        a = base + math.radians(extra)
        ox = cx + nx * p.gap / 2 * (1 if k else -1)
        oy = cy + ny * p.gap / 2 * (1 if k else -1)
        c, s = math.cos(a), math.sin(a)
        out.append(S.line(ox - c * half, oy - s * half, ox + c * half,
                          oy + s * half, 0.008, ink))
        if p.level.hatched:
            slant = a + (1 if k else -1) * p.hatch * 0.9
            for j in range(-5, 6):
                hx, hy = ox + c * half * j / 5.5, oy + s * half * j / 5.5
                out.append(S.line(hx - math.cos(slant) * 0.035,
                                  hy - math.sin(slant) * 0.035,
                                  hx + math.cos(slant) * 0.035,
                                  hy + math.sin(slant) * 0.035, 0.004,
                                  (130, 130, 140)))
    return out
