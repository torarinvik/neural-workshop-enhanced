# -*- coding: utf-8 -*-
"""Longer Line: which line is the longest?

Lines on a page. Which is longest? From rung 4 they lie at different
angles; from rung 7 they carry fins -- arrowheads make a line look
shorter, tails longer (Mueller-Lyer) -- and the fins are dealt against
the truth; from rung 10 the lines lie between converging rails, where
the one nearer the narrow end looks longer (Ponzo), whichever
really is.

The ladder:

* rungs 1-3: two level lines, one half as long again;
* rungs 4-6: at any angle; a fifth longer;
* rungs 7-9: fins that mislead; an eighth;
* rungs 10-12: stacked between converging rails; a twelfth;
* from rung 13: three lines, then four; the difference narrowing
  toward one part in fifty.

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
    lines: int
    ratio: float
    angles: bool
    fins: bool
    rails: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        lines=2 if r < 13 else 3 if r < 19 else 4,
        ratio=(1.5 if r < 4 else 1.2 if r < 7 else 1.125 if r < 10
               else 1.085 if r < 13 else max(1.02, 1.07 - 0.003 * (r - 13))),
        angles=r >= 4,
        fins=7 <= r < 10 or r >= 13,
        rails=10 <= r < 13)


class Line(NamedTuple):
    x: float
    y: float
    length: float
    angle: float
    fins: int            # 0 none, 1 arrowheads (looks shorter), -1 tails


class Puzzle(NamedTuple):
    level: Grade
    lines: List[Line]
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    lengths = [ln.length for ln in p.lines]
    return lengths.index(max(lengths))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.lines
    base = draw.uniform(0.22, 0.3)
    answer = S.slot(seed, n)
    lines = []
    w = S.W / n
    for k in range(n):
        length = base * level.ratio if k == answer else \
            base * draw.uniform(0.985, 1.0)
        angle = draw.uniform(0, math.pi) if level.angles else 0.0
        if level.rails:
            angle = 0.0
        fins = 0
        if level.fins:
            fins = 1 if k == answer else -1
        y = 0.5 + (draw.uniform(-0.12, 0.12) if not level.rails else 0)
        lines.append(Line((k + 0.5) * w, y, length, angle, fins))
    if level.rails:
        # Stacked between rails that narrow upward, where the upper line
        # looks the longer whichever is: port 0 is the lowest.
        for k in range(n):
            lines[k] = lines[k]._replace(x=S.W / 2, y=0.25 + 0.5 * k / (n - 1))
    names = (_('Lower'), _('Upper')) if n == 2 and level.rails else \
        (_('Left'), _('Right')) if n == 2 else \
        tuple(str(k + 1) for k in range(n))
    return Puzzle(level, lines, draw.random(), draw.choice(S.PAPERS),
                  _('Which line is the longest?'), names, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    ink = S.hsv(p.hue, 0.6, 0.45)
    if p.level.rails:
        for s in (-1, 1):
            out.append(S.line(S.W / 2 + s * 0.6, 0.05, S.W / 2 + s * 0.12,
                              0.95, 0.006, (150, 150, 160)))
    for k, ln in enumerate(p.lines):
        c, s = math.cos(ln.angle), math.sin(ln.angle)
        ax, ay = ln.x - c * ln.length / 2, ln.y - s * ln.length / 2
        bx, by = ln.x + c * ln.length / 2, ln.y + s * ln.length / 2
        out.append(S.line(ax, ay, bx, by, 0.009, ink))
        if ln.fins:
            f = 0.045
            for (ex, ey), d in (((ax, ay), 1), ((bx, by), -1)):
                for side in (-1, 1):
                    a = ln.angle + side * 0.7
                    out.append(S.line(
                        ex, ey, ex + d * ln.fins * math.cos(a) * f,
                        ey + d * ln.fins * math.sin(a) * f, 0.007, ink))
        if not p.level.rails:
            w = S.W / len(p.lines)
            out.append(S.hit(k * w + 0.01, 0.03, w - 0.02, 0.94, k))
            if len(p.lines) > 2:
                out.append(S.text(k * w + 0.06, 0.92, 0.045, str(k + 1)))
        elif len(p.lines) > 2:
            out.append(S.text(S.W / 2 - 0.7, ln.y, 0.045, str(k + 1)))
    return out
