# -*- coding: utf-8 -*-
"""Bump or Dent: read a surface's shape from its shading.

Round marks on a wall, each shaded from one side to the other. A bump
is lit on the side facing the lamp and a dent on the side away from it,
so the same picture turned upside down changes from one into the other.
Low down a lamp is drawn and the question is of one mark: bump or dent?
Then the lamp goes and a mark known to be a bump is given instead;
then there are several marks, and the question is how many are bumps.

The ladder:

* rungs 1-3: one mark; the lamp above or below;
* rungs 4-6: the lamp anywhere round;
* rungs 7-9: no lamp: a mark labelled as a bump shows where the light
  is;
* rungs 10-12: four to six marks and a lamp: how many are bumps?
* from rung 13: counting from a labelled bump; more marks and fainter
  shading every few rungs.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

BUMP, DENT = 0, 1


class Grade(NamedTuple):
    rung: int
    marks: Tuple[int, int]
    lamp: bool           # drawn; else a labelled bump
    around: bool         # the light from anywhere, not just above or below
    count: bool
    depth: float         # how strongly shaded


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        marks=((1, 1) if r < 10 else (4, 6) if r < 13
               else (5, min(9, 7 + (r - 13) // 3))),
        lamp=r < 7 or 10 <= r < 13,
        around=r >= 4,
        count=r >= 10,
        depth=0.3 if r < 13 else max(0.08, 0.26 - 0.012 * (r - 13)))


class Mark(NamedTuple):
    x: float
    y: float
    r: float
    lit: float           # the direction of its brightest edge, radians


class Puzzle(NamedTuple):
    level: Grade
    light: float                 # where the light comes from, radians
    marks: List[Mark]
    guide: Optional[Mark]        # a mark that is a bump, when no lamp
    tone: float
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def is_bump(light: float, m: Mark) -> bool:
    return math.cos(m.lit - light) > 0


def solve(p: Puzzle) -> int:
    light = p.light if p.guide is None else p.guide.lit
    bumps = sum(is_bump(light, m) for m in p.marks)
    if p.level.count:
        return bumps
    return BUMP if bumps else DENT


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = draw.randint(*level.marks)
    light = draw.uniform(0, 2 * math.pi) if level.around else \
        draw.choice((math.pi / 2, -math.pi / 2))
    if level.count:
        bumps = S.slot(seed, n + 1)
        kinds = [True] * bumps + [False] * (n - bumps)
        draw.shuffle(kinds)
        answer = bumps
        q = _('How many are bumps?')
        choices = tuple(str(k) for k in range(n + 1))
    else:
        answer = S.slot(seed, 2)
        kinds = [answer == BUMP]
        q = _('Bump or dent?')
        choices = (_('Bump'), _('Dent'))
    # Places on a loose grid, clear of the lamp's corner and the guide's.
    cells = [(cx, cy) for cx in range(4) for cy in range(2)] if n > 1 else \
        [(1.5, 0.5)]
    if n > 8:
        cells = [(cx, cy) for cx in range(5) for cy in range(2)]
    draw.shuffle(cells)
    cols = 5.0 if n > 8 else 4.0
    marks = []
    for k in range(n):
        cx, cy = cells[k]
        r = 0.2 if n == 1 else draw.uniform(0.075, 0.1)
        if n == 1:
            x, y = S.W / 2, 0.45
        else:
            x = 0.2 + (cx + 0.5) * 1.3 / cols + draw.uniform(-0.03, 0.03)
            y = 0.1 + (cy + 0.5) * 0.36 + draw.uniform(-0.03, 0.03)
        marks.append(Mark(x, y, r, light if kinds[k] else light + math.pi))
    guide = None if level.lamp else Mark(0.14, 0.86, 0.075, light)
    return Puzzle(level, light, marks, guide, draw.uniform(0.5, 0.65),
                  draw.random(), draw.choice(S.PAPERS), q, choices, answer)


def shaded(m: Mark, tone: float, depth: float, hue: float) -> list:
    """A disc shaded across, brightest toward m.lit."""
    out = []
    bands = 14
    ux, uy = math.cos(m.lit), math.sin(m.lit)
    for b in range(bands):
        d0 = -m.r + 2 * m.r * b / bands
        d1 = d0 + 2 * m.r / bands * 1.04
        d1 = min(d1, m.r)
        h0 = math.sqrt(max(0.0, m.r ** 2 - d0 ** 2))
        h1 = math.sqrt(max(0.0, m.r ** 2 - d1 ** 2))
        v = tone + depth * ((b + 0.5) / bands * 2 - 1)
        out.append(S.poly((
            (m.x + ux * d0 + uy * h0, m.y + uy * d0 - ux * h0),
            (m.x + ux * d0 - uy * h0, m.y + uy * d0 + ux * h0),
            (m.x + ux * d1 - uy * h1, m.y + uy * d1 + ux * h1),
            (m.x + ux * d1 + uy * h1, m.y + uy * d1 - ux * h1)),
            S.grey(v, 0.05, hue)))
    return out


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = [S.rect(0.0, 0.0, S.W, 1.0, S.grey(p.tone, 0.05, p.hue))]
    for m in p.marks:
        out += shaded(m, p.tone, p.level.depth, p.hue)
        if judged:
            out.append(S.text(m.x, m.y - m.r - 0.04, 0.035,
                              _('bump') if is_bump(p.light, m) else _('dent')))
    if p.guide is not None:
        out += shaded(p.guide, p.tone, p.level.depth, p.hue)
        out.append(S.text(p.guide.x + 0.2, p.guide.y, 0.04, _('a bump')))
    if p.level.lamp:
        cx, cy = S.W / 2, 0.5
        lx = cx + math.cos(p.light) * 0.68
        ly = cy + math.sin(p.light) * 0.41
        gold = (250, 215, 80)
        for k in range(8):
            a = k * math.pi / 4
            out.append(S.line(lx + math.cos(a) * 0.035, ly + math.sin(a) * 0.035,
                              lx + math.cos(a) * 0.06, ly + math.sin(a) * 0.06,
                              0.006, gold))
        out.append(S.disc(lx, ly, 0.028, gold))
    return out
