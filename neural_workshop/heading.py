# -*- coding: utf-8 -*-
"""Heading: where are you going?

Dots streaming outward, as the world does to someone moving through
it: everything flows away from the one point being headed for. Along a
line across the page stand some numbered marks. Which one are you
heading for? The point itself is no brighter than anywhere else; it is
where the flow comes from.

The ladder:

* rungs 1-3: two marks, far apart;
* rungs 4-6: three;
* rungs 7-9: four; one dot in five moves any way at all;
* rungs 10-12: five, closer; three in ten; shorter-lived dots;
* from rung 13: seven marks closing up, and more stray dots.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

DOTS = 150
RATE = 0.9           # how fast a dot's distance from the point grows
LINE = 0.5


class Grade(NamedTuple):
    rung: int
    marks: int
    apart: float
    stray: float         # the share of dots going any way
    life: float
    show: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        marks=2 if r < 4 else 3 if r < 7 else 4 if r < 10 else 5 if r < 13 else 7,
        apart=(0.7 if r < 4 else 0.4 if r < 7 else 0.25 if r < 10
               else 0.18 if r < 13 else max(0.06, 0.15 * 0.93 ** (r - 13))),
        stray=(0.0 if r < 7 else 0.2 if r < 10 else 0.3 if r < 13
               else min(0.6, 0.35 + 0.02 * (r - 13))),
        life=1.5 if r < 10 else 0.9 if r < 13 else 0.7,
        show=3.5)


class Puzzle(NamedTuple):
    level: Grade
    seed: int
    marks: Tuple[float, ...]     # along the line
    phases: Tuple[float, ...]
    hue: float
    paper: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def dots(p: Puzzle, t: float) -> List[Tuple[float, float, float, float]]:
    """Every dot at time t: where it is and how fast it is going."""
    fx, fy = p.marks[p.answer], LINE
    stray = int(round(DOTS * p.level.stray))
    life = p.level.life
    out = []
    for i, phase in enumerate(p.phases):
        age = (t + phase) % life
        born = S.stream(p.seed, i, int((t + phase) // life))
        x, y = born.random() * S.W, born.random()
        if i < stray:
            a = born.uniform(0, 2 * math.pi)
            v = born.uniform(0.05, 0.4)
            vx, vy = math.cos(a) * v, math.sin(a) * v
            out.append((x + vx * age, y + vy * age, vx, vy))
        else:
            g = math.exp(RATE * age)
            px, py = fx + (x - fx) * g, fy + (y - fy) * g
            out.append((px, py, (px - fx) * RATE, (py - fy) * RATE))
    return out


def source(p: Puzzle) -> Tuple[float, float]:
    """The point the flow comes from: the one nearest the lines of
    travel of the dots -- of those that pass near it at all, since the
    strays' lines pass anywhere."""
    lines = []
    for t in (0.4, 1.2, 2.0, 2.8):
        for x, y, vx, vy in dots(p, t):
            v = math.hypot(vx, vy)
            if v > 1e-6:
                nx, ny = -vy / v, vx / v
                lines.append((nx, ny, nx * x + ny * y))
    at = None
    for within in (None, 0.4, 0.2, 0.1, 0.05, 0.03):
        a11 = a12 = a22 = b1 = b2 = 0.0
        for nx, ny, d in lines:
            if at is not None and abs(nx * at[0] + ny * at[1] - d) > within:
                continue
            a11 += nx * nx
            a12 += nx * ny
            a22 += ny * ny
            b1 += nx * d
            b2 += ny * d
        det = a11 * a22 - a12 * a12
        if abs(det) < 1e-12:
            break
        at = ((b1 * a22 - b2 * a12) / det, (a11 * b2 - a12 * b1) / det)
    return at


def solve(p: Puzzle) -> int:
    x, _y = source(p)
    gaps = [abs(m - x) for m in p.marks]
    return gaps.index(min(gaps))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    n = level.marks
    answer = S.slot(seed, n)
    names = (_('Left'), _('Right')) if n == 2 else \
        tuple(str(k + 1) for k in range(n))
    for k in range(60):
        draw = random.Random(seed + k * 7919)
        width = level.apart * (n - 1)
        first = draw.uniform(0.2, S.W - 0.2 - width)
        marks = tuple(first + i * level.apart for i in range(n))
        p = Puzzle(level, seed + k, marks,
                   tuple(draw.random() * level.life for _i in range(DOTS)),
                   draw.random(), (26, 28, 36), 0.8, level.show + 6.0, (), (),
                   _('Which mark are you heading for?'), names, answer)
        if solve(p) == answer:
            return p
    raise RuntimeError('no flow for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    ink = S.hsv(p.hue, 0.15, 0.95)
    if t < p.level.show and not judged:
        for x, y, _vx, _vy in dots(p, t):
            if 0 <= x <= S.W and 0 <= y <= 1:
                out.append(S.disc(x, y, 0.008, ink))
    gold = (250, 215, 80)
    for k, m in enumerate(p.marks):
        colour = (215, 60, 60) if judged and k == p.answer else gold
        out.append(S.line(m, LINE - 0.035, m, LINE + 0.035, 0.005, colour))
        if len(p.marks) > 2:
            out.append(S.text(m, LINE - 0.075 - 0.05 * (k % 2), 0.035, str(k + 1),
                              (230, 230, 235)))
        half = max(0.02, min(0.08, p.level.apart / 2))
        out.append(S.hit(m - half, LINE - 0.14, 2 * half, 0.2, k))
    return out
