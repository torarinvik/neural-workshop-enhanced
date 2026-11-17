# -*- coding: utf-8 -*-
"""What Share: how much of it is coloured?

A bar, a round or a scatter of dots, part of it coloured. What share
is that? The same question in three guises, so that what is learnt is
the share and not the look of a bar.

The ladder:

* rungs 1-3: a bar or a round; three answers a quarter apart;
* rungs 4-6: four answers, fifteen in a hundred apart; the round
  starts anywhere;
* rungs 7-9: ten apart; the coloured part in two pieces;
* rungs 10-12: seven apart; scatters of dots too;
* from rung 13: five answers, six from rung 16, closing toward three
  in a hundred.

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
    answers: int
    apart: int           # in a hundred
    pieces: int
    guises: Tuple[str, ...]


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        answers=3 if r < 4 else 4 if r < 13 else 5 if r < 16 else 6,
        apart=(25 if r < 4 else 15 if r < 7 else 10 if r < 10 else 7 if r < 13
               else max(3, 6 - (r - 13) // 3)),
        pieces=1 if r < 7 else 2,
        guises=('bar', 'round') if r < 10 else ('bar', 'round', 'dots'))


class Puzzle(NamedTuple):
    level: Grade
    guise: str
    pieces: List[Tuple[float, float]]    # each (start, length), shares of 1
    dots: List[Tuple[float, float, bool]]
    turn: float
    hues: Tuple[float, float]
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def share(p: Puzzle) -> float:
    if p.guise == 'dots':
        return sum(1 for d in p.dots if d[2]) / float(len(p.dots))
    return sum(length for _s, length in p.pieces)


def solve(p: Puzzle) -> int:
    s = share(p) * 100
    gaps = [abs(int(c.rstrip('%')) - s) for c in p.choices]
    return gaps.index(min(gaps))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.answers
    first = draw.randint(8, 92 - level.apart * (n - 1))
    values = [first + k * level.apart for k in range(n)]
    answer = S.slot(seed, n)
    s = values[answer] / 100.0
    guise = draw.choice(level.guises)
    pieces: List[Tuple[float, float]] = []
    dots: List[Tuple[float, float, bool]] = []
    if guise == 'dots':
        total = 100
        flags = [k < values[answer] for k in range(total)]
        draw.shuffle(flags)
        spots = [(cx, cy) for cx in range(14) for cy in range(9)]
        draw.shuffle(spots)
        for k in range(total):
            cx, cy = spots[k]
            dots.append((0.12 + (cx + 0.5) * 1.36 / 14 + draw.uniform(-0.02, 0.02),
                         0.06 + (cy + 0.5) * 0.88 / 9 + draw.uniform(-0.02, 0.02),
                         flags[k]))
    elif level.pieces == 1:
        pieces = [(0.0, s)]
    else:
        a = s * draw.uniform(0.3, 0.7)
        gap = (1 - s) * draw.uniform(0.25, 0.6)
        lead = (1 - s - gap) * draw.random() if guise == 'bar' else 0.0
        pieces = [(lead, a), (lead + a + gap, s - a)]
    return Puzzle(level, guise, pieces, dots,
                  draw.uniform(0, 2 * math.pi) if level.rung >= 4 else math.pi / 2,
                  (draw.random(), draw.random()), draw.choice(S.PAPERS),
                  _('What share is coloured?'),
                  tuple('%d%%' % v for v in values), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    full = S.hsv(p.hues[0], 0.65, 0.85)
    rest = S.hsv(p.hues[0], 0.08, 0.86)
    edge = S.hsv(p.hues[0], 0.4, 0.4)
    out = []
    if p.guise == 'dots':
        for x, y, on in p.dots:
            out.append(S.disc(x, y, 0.024, full if on else S.hsv(
                p.hues[0] + 0.5, 0.25, 0.6)))
    elif p.guise == 'bar':
        x0, w, y, h = 0.15, S.W - 0.3, 0.38, 0.24
        out.append(S.rect(x0, y, w, h, rest))
        for start, length in p.pieces:
            out.append(S.rect(x0 + start * w, y, length * w, h, full))
        for a, b, c, d in ((x0, y, x0 + w, y), (x0, y + h, x0 + w, y + h),
                           (x0, y, x0, y + h), (x0 + w, y, x0 + w, y + h)):
            out.append(S.line(a, b, c, d, 0.005, edge))
    else:
        cx, cy, r = S.W / 2, 0.5, 0.42
        out.append(S.disc(cx, cy, r, rest))
        for start, length in p.pieces:
            steps = max(2, int(96 * length))
            pts = [(cx, cy)]
            for k in range(steps + 1):
                a = p.turn - 2 * math.pi * (start + length * k / steps)
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
            # In slices no more than a third of a turn: each stays convex.
            cut = max(1, steps // 4)
            for k in range(1, len(pts) - 1, cut):
                out.append(S.poly([pts[0]] + pts[k:k + cut + 1], full))
        out.append(S.ring(cx, cy, r, 0.005, edge))
    if judged:
        out.append(S.text(S.W / 2, 0.04, 0.045, '%d%%' % round(share(p) * 100)))
    return out
