# -*- coding: utf-8 -*-
"""Texture Edge: where is the patch that is different?

A page covered in small strokes that all lean one way, except in one
square patch, where they lean another. No outline is drawn: the patch
shows only as a change of texture. Which part of the page is it in?
From rung 7 the texture is sometimes made of little figures instead --
crosses among corners, the same two strokes arranged differently -- at
every angle.

The ladder:

* rungs 1-3: left or right; a big patch at right angles to the rest;
* rungs 4-6: four quarters; sixty degrees off; strokes a little
  untidy;
* rungs 7-9: forty-five degrees, a smaller patch; figures too;
* rungs 10-12: thirty degrees;
* from rung 13: a patch of four strokes, and the lean between closing
  toward ten degrees.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

CELL = 0.1
COLS, ROWS = 16, 10
LINE, CORNER, CROSS = 0, 1, 2


class Grade(NamedTuple):
    rung: int
    regions: int
    lean: float          # degrees between patch and ground
    jitter: float
    patch: int           # cells along its side
    figures: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    lean = (90.0 if r < 4 else 60.0 if r < 7 else 45.0 if r < 10
            else 30.0 if r < 13 else max(10.0, 26.0 - 1.2 * (r - 13)))
    return Grade(
        rung=r,
        regions=2 if r < 4 else 4,
        lean=lean,
        jitter=0.0 if r < 4 else min(10.0, lean * 0.25),
        patch=4 if r < 7 else 3 if r < 13 else 2,
        figures=r >= 7)


class Mark(NamedTuple):
    x: float
    y: float
    angle: float
    kind: int


class Puzzle(NamedTuple):
    level: Grade
    guise: str                   # 'lean' or 'figure'
    marks: List[List[Mark]]      # marks[col][row]
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def region(level: Grade, x: float, y: float) -> int:
    right = 1 if x >= S.W / 2 else 0
    if level.regions == 2:
        return right
    return (0 if y >= 0.5 else 2) + right


def oddness(p: Puzzle) -> List[List[float]]:
    """How unlike the rest each mark is."""
    flat = [m for col in p.marks for m in col]
    if p.guise == 'figure':
        kinds = [m.kind for m in flat]
        common = max(set(kinds), key=kinds.count)
        return [[float(m.kind != common) for m in col] for col in p.marks]
    cx = sum(math.cos(2 * m.angle) for m in flat)
    cy = sum(math.sin(2 * m.angle) for m in flat)
    mean = math.atan2(cy, cx) / 2

    def off(a):
        d = (a - mean) % math.pi
        return min(d, math.pi - d)
    return [[off(m.angle) for m in col] for col in p.marks]


def solve(p: Puzzle) -> int:
    odd = oddness(p)
    s = p.level.patch
    best, where = -1.0, (0, 0)
    for cx in range(COLS - s + 1):
        for cy in range(ROWS - s + 1):
            total = sum(odd[cx + i][cy + j] for i in range(s) for j in range(s))
            if total > best:
                best, where = total, (cx, cy)
    return region(p.level, (where[0] + s / 2.0) * CELL,
                  (where[1] + s / 2.0) * CELL)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, level.regions)
    guise = 'figure' if level.figures and draw.random() < 0.4 else 'lean'
    s = level.patch
    half_c, half_r = COLS // 2, ROWS // 2
    if level.regions == 2:
        c0, r0, cw, rh = answer * half_c, 0, half_c, ROWS
    else:
        c0, r0, cw, rh = (answer % 2) * half_c, (half_r if answer < 2 else 0), \
            half_c, half_r
    px = c0 + draw.randrange(cw - s + 1)
    py = r0 + draw.randrange(rh - s + 1)
    base = draw.uniform(0, math.pi)
    sign = draw.choice((-1, 1))
    ground_kind, patch_kind = draw.choice(((CORNER, CROSS), (CROSS, CORNER)))
    marks = []
    for cx in range(COLS):
        col = []
        for cy in range(ROWS):
            inside = px <= cx < px + s and py <= cy < py + s
            x = (cx + 0.5) * CELL + draw.uniform(-0.012, 0.012)
            y = (cy + 0.5) * CELL + draw.uniform(-0.012, 0.012)
            if guise == 'figure':
                col.append(Mark(x, y, draw.uniform(0, 2 * math.pi),
                                patch_kind if inside else ground_kind))
            else:
                a = base + (math.radians(level.lean) * sign if inside else 0)
                a += math.radians(draw.uniform(-level.jitter, level.jitter))
                col.append(Mark(x, y, a % math.pi, LINE))
        marks.append(col)
    names = (_('Left'), _('Right')) if level.regions == 2 else \
        (_('Top left'), _('Top right'), _('Bottom left'), _('Bottom right'))
    return Puzzle(level, guise, marks, draw.random(), draw.choice(S.PAPERS),
                  _('Which part holds the patch that is different?'), names,
                  answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    ink = S.hsv(p.hue, 0.5, 0.35)
    out = []
    r = 0.03
    for col in p.marks:
        for m in col:
            c, s = math.cos(m.angle) * r, math.sin(m.angle) * r
            if m.kind == LINE:
                out.append(S.line(m.x - c, m.y - s, m.x + c, m.y + s, 0.006, ink))
            elif m.kind == CROSS:
                out.append(S.line(m.x - c, m.y - s, m.x + c, m.y + s, 0.005, ink))
                out.append(S.line(m.x + s, m.y - c, m.x - s, m.y + c, 0.005, ink))
            else:
                # A corner: the cross's two strokes, joined at their ends.
                ax, ay = m.x - c / 2 + s / 2, m.y - s / 2 - c / 2
                out.append(S.line(ax, ay, ax + 2 * c, ay + 2 * s, 0.005, ink))
                out.append(S.line(ax, ay, ax - 2 * s, ay + 2 * c, 0.005, ink))
    half = S.W / 2
    for k in range(p.level.regions):
        if p.level.regions == 2:
            box = (k * half, 0.0, half, 1.0)
        else:
            box = ((k % 2) * half, 0.5 if k < 2 else 0.0, half, 0.5)
        out.append(S.hit(box[0] + 0.004, box[1] + 0.004, box[2] - 0.008,
                         box[3] - 0.008, k))
    return out
