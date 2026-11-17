# -*- coding: utf-8 -*-
"""Faster: which is moving faster?

Two windows with dots moving in each. In which are they moving faster?
A big dot looks slower than a small one at the same speed, and a short
hop is easier to see than a long glide, so higher up the faster dots
are the bigger ones, the two windows move different ways, and at last
they are shown one after the other.

The ladder:

* rungs 1-3: one dot in each, the same way; one three fifths faster;
* rungs 4-6: three dots; the faster ones bigger; a third faster;
* rungs 7-9: eight dots, the windows moving different ways; a fifth;
* rungs 10-12: an eighth;
* from rung 13: one window after the other; closing toward one part
  in thirty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

BOXES = ((0.05, 0.15, 0.7, 0.7), (0.85, 0.15, 0.7, 0.7))


class Grade(NamedTuple):
    rung: int
    dots: int
    ratio: float
    sizes: bool
    ways: bool
    turns: bool          # one after the other


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        dots=1 if r < 4 else 3 if r < 7 else 8,
        ratio=(1.6 if r < 4 else 1.33 if r < 7 else 1.2 if r < 10
               else 1.125 if r < 13 else max(1.035, 1.1 - 0.004 * (r - 13))),
        sizes=r >= 4,
        ways=r >= 7,
        turns=r >= 13)


class Puzzle(NamedTuple):
    level: Grade
    speeds: Tuple[float, float]
    ways: Tuple[float, float]
    sizes: Tuple[float, float]
    starts: Tuple[Tuple[Tuple[float, float], ...], ...]
    spans: Tuple[Tuple[float, float], Tuple[float, float]]   # when each shows
    hue: float
    paper: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def dots(p: Puzzle, k: int, t: float) -> List[Tuple[float, float]]:
    """Window k's dots at time t (empty when it is not showing)."""
    t0, t1 = p.spans[k]
    if not t0 <= t < t1:
        return []
    bx, by, bw, bh = BOXES[k]
    dx = math.cos(p.ways[k]) * p.speeds[k] * t
    dy = math.sin(p.ways[k]) * p.speeds[k] * t
    return [(bx + (x + dx) % bw, by + (y + dy) % bh) for x, y in p.starts[k]]


def solve(p: Puzzle) -> int:
    # Each window's speed, measured from how far a dot goes in a moment.
    seen = []
    for k in range(2):
        t = (p.spans[k][0] + p.spans[k][1]) / 2
        _bx, _by, bw, bh = BOXES[k]
        best = 0.0
        for a, b in zip(dots(p, k, t), dots(p, k, t + 0.02)):
            dx = (b[0] - a[0] + bw / 2) % bw - bw / 2
            dy = (b[1] - a[1] + bh / 2) % bh - bh / 2
            best = max(best, math.hypot(dx, dy) / 0.02)
        seen.append(best)
    return seen.index(max(seen))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, 2)
    slow = draw.uniform(0.14, 0.24)
    speeds = [slow, slow]
    speeds[answer] = slow * level.ratio
    way = draw.choice((0.0, math.pi, math.pi / 2, -math.pi / 2))
    ways = [way, way]
    if level.ways:
        ways[1] = way + draw.choice((math.pi / 2, math.pi, -math.pi / 2))
    sizes = [0.022, 0.022]
    if level.sizes:
        sizes = [0.016, 0.016]
        sizes[answer] = 0.03
    starts = tuple(tuple((draw.random() * BOXES[k][2], draw.random() * BOXES[k][3])
                         for _i in range(level.dots)) for k in range(2))
    if level.turns:
        spans = ((0.5, 2.0), (2.5, 4.0))
    else:
        spans = ((0.0, 3.5), (0.0, 3.5))
    end = spans[1][1]
    return Puzzle(level, tuple(speeds), tuple(ways), tuple(sizes), starts, spans,
                  draw.random(), (26, 28, 36), spans[1][0] + 0.8, end + 6.0,
                  (), (), _('In which window are the dots moving faster?'),
                  (_('Left'), _('Right')), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    ink = S.hsv(p.hue, 0.2, 0.95)
    for k, (bx, by, bw, bh) in enumerate(BOXES):
        out.append(S.rect(bx, by, bw, bh, (44, 47, 58)))
        if not judged:
            for x, y in dots(p, k, t):
                out.append(S.disc(x, y, p.sizes[k], ink))
        else:
            out.append(S.text(bx + bw / 2, by + bh / 2, 0.06,
                              '%.0f' % (p.speeds[k] * 100), (230, 230, 235)))
        out.append(S.hit(bx, by, bw, bh, k))
    return out
