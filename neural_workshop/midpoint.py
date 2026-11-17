# -*- coding: utf-8 -*-
"""Midpoint: which mark is in the middle?

A line with marks across it. Which mark is exactly halfway along? From
rung 4 the line lies at any angle; from rung 7 its ends carry fins that
make one half look longer; from rung 10 there is no line at all, only
two end dots and the marks between.

The ladder:

* rungs 1-3: three marks, an eighth of the line apart;
* rungs 4-6: at any angle; a twelfth apart;
* rungs 7-9: fins at the ends; a twentieth;
* rungs 10-12: no line; four marks;
* from rung 13: five marks, narrowing toward one part in a hundred.

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
    marks: int
    apart: float         # between marks, as a share of the line
    angles: bool
    fins: bool
    bare: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        marks=3 if r < 10 else 4 if r < 13 else 5,
        apart=(0.125 if r < 4 else 0.083 if r < 7 else 0.05 if r < 10
               else 0.04 if r < 13 else max(0.01, 0.035 * 0.9 ** (r - 13))),
        angles=r >= 4,
        fins=7 <= r < 10 or r >= 13,
        bare=r >= 10)


class Puzzle(NamedTuple):
    level: Grade
    a: Tuple[float, float]
    b: Tuple[float, float]
    marks: List[float]           # each, as a share of the way from a to b
    fins: int                    # which end's fins point in: 0 none, 1 a, -1 b
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    return min(range(len(p.marks)), key=lambda k: abs(p.marks[k] - 0.5))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.marks
    answer = S.slot(seed, n)
    marks = [0.5 + (k - answer) * level.apart for k in range(n)]
    angle = draw.uniform(-math.pi / 2, math.pi / 2) if level.angles else 0.0
    half = draw.uniform(0.32, 0.42)
    cx, cy = S.W / 2, 0.5
    a = (cx - math.cos(angle) * half, cy - math.sin(angle) * half)
    b = (cx + math.cos(angle) * half, cy + math.sin(angle) * half)
    fins = draw.choice((1, -1)) if level.fins else 0
    return Puzzle(level, a, b, marks, fins, draw.random(),
                  draw.choice(S.PAPERS), _('Which mark is exactly halfway?'),
                  tuple(str(k + 1) for k in range(n)), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    ink = S.hsv(p.hue, 0.6, 0.45)
    (ax, ay), (bx, by) = p.a, p.b
    out = []
    if not p.level.bare:
        out.append(S.line(ax, ay, bx, by, 0.008, ink))
    out += [S.disc(ax, ay, 0.012, ink), S.disc(bx, by, 0.012, ink)]
    ang = math.atan2(by - ay, bx - ax)
    if p.fins:
        for (ex, ey), d in (((ax, ay), p.fins), ((bx, by), p.fins)):
            for side in (-1, 1):
                a = ang + side * 0.7
                out.append(S.line(ex, ey, ex + d * math.cos(a) * 0.05,
                                  ey + d * math.sin(a) * 0.05, 0.006, ink))
    nx, ny = -math.sin(ang), math.cos(ang)
    n = len(p.marks)
    ux, uy = math.cos(ang), math.sin(ang)
    length = math.hypot(bx - ax, by - ay)
    mid = sum(p.marks) / n
    mx, my = ax + (bx - ax) * mid, ay + (by - ay) * mid
    step = max(0.075, p.level.apart * length)
    for k, m in enumerate(p.marks):
        x, y = ax + (bx - ax) * m, ay + (by - ay) * m
        out.append(S.line(x - nx * 0.03, y - ny * 0.03, x + nx * 0.03,
                          y + ny * 0.03, 0.004, (200, 60, 60)))
        # The numbers fan out, each led to its mark.
        along = (k - (n - 1) / 2.0) * step
        lx, ly = mx + ux * along + nx * 0.15, my + uy * along + ny * 0.15
        out.append(S.line(x + nx * 0.035, y + ny * 0.035, lx - nx * 0.03,
                          ly - ny * 0.03, 0.002, (150, 150, 160)))
        out.append(S.text(lx, ly, 0.04, str(k + 1)))
    return out
