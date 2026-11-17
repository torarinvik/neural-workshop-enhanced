# -*- coding: utf-8 -*-
"""Bigger Area: which shape covers the most paper?

Shapes on a page. Which has the greatest area? A long thin shape looks
bigger than a compact one of the same area, so from rung 4 the smaller
shapes are the longer ones; from rung 7 the shapes are free outlines,
all different.

The ladder:

* rungs 1-3: two like shapes, one bigger by three fifths;
* rungs 4-6: a compact shape against a long one; by a third;
* rungs 7-9: free outlines; by a fifth;
* rungs 10-12: by an eighth, turned any way;
* from rung 13: three shapes, then four; narrowing toward one part
  in thirty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _


class Grade(NamedTuple):
    rung: int
    shapes: int
    ratio: float
    long: bool
    free: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        shapes=2 if r < 13 else 3 if r < 19 else 4,
        ratio=(1.6 if r < 4 else 1.33 if r < 7 else 1.2 if r < 10
               else 1.125 if r < 13 else max(1.035, 1.1 - 0.004 * (r - 13))),
        long=r >= 4,
        free=r >= 7)


Outline = Tuple[Tuple[float, float], ...]


class Puzzle(NamedTuple):
    level: Grade
    outlines: List[Outline]      # already placed on the page
    hues: List[float]
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    areas = [S.area(o) for o in p.outlines]
    return areas.index(max(areas))


def _unit(level: Grade, draw: random.Random, stretch: float):
    if level.free:
        pts = S.blob(draw, 4, 0.2)
    else:
        kind = draw.choice(('disc', 'box', 'tri'))
        if kind == 'disc':
            pts = [(math.cos(2 * math.pi * k / 48), math.sin(2 * math.pi * k / 48))
                   for k in range(48)]
        elif kind == 'box':
            pts = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        else:
            pts = [(-1, -0.8), (1, -0.8), (0, 1)]
    return [(x * stretch, y / stretch) for x, y in pts]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.shapes
    answer = S.slot(seed, n)
    base = draw.uniform(0.05, 0.065)
    w = S.W / n
    for _attempt in range(200):
        outlines = []
        for k in range(n):
            want = base * level.ratio if k == answer else \
                base * draw.uniform(0.97, 1.0)
            want /= (n / 2.0) ** 0.9
            stretch = 1.0
            if level.long:
                stretch = 1.0 if k == answer else draw.uniform(1.5, 1.9)
            pts = _unit(level, draw, stretch)
            scale = math.sqrt(want / S.area(pts))
            turn = draw.uniform(0, math.pi) if level.rung >= 10 else \
                draw.choice((0.0, math.pi / 2)) if level.long else 0.0
            outlines.append(tuple(S.place(pts, (k + 0.5) * w, 0.5, scale, turn)))
        if all(0.01 < x < S.W - 0.01 and 0.03 < y < 0.97
               for o in outlines for x, y in o) and all(
                   k * w < x < (k + 1) * w for k, o in enumerate(outlines)
                   for x, _y in o):
            break
        base *= 0.93
    names = (_('Left'), _('Right')) if n == 2 else \
        tuple(str(k + 1) for k in range(n))
    return Puzzle(level, outlines, [draw.random() for _k in range(n)],
                  draw.choice(S.PAPERS), _('Which shape has the greatest area?'),
                  names, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    w = S.W / len(p.outlines)
    for k, o in enumerate(p.outlines):
        out.append(S.poly(o, S.hsv(p.hues[k], 0.55, 0.8)))
        out.append(S.hit(k * w + 0.01, 0.03, w - 0.02, 0.94, k))
        if len(p.outlines) > 2:
            out.append(S.text(k * w + 0.06, 0.92, 0.045, str(k + 1)))
    return out
