# -*- coding: utf-8 -*-
"""Steeper: which line is the steeper?

Two slopes. Which is steeper -- nearer to upright? From rung 4 the
lines differ in length; from rung 7 one climbs to the right and the
other to the left, so they cannot be laid over each other; from rung
10 each sits in a tilted frame, which drags how upright it looks.

The ladder:

* rungs 1-3: twenty-five degrees apart;
* rungs 4-6: twelve; different lengths;
* rungs 7-9: six; one climbing each way;
* rungs 10-12: four; tilted frames;
* from rung 13: narrowing toward half a degree.

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
    apart: float         # degrees
    lengths: bool
    mirrored: bool
    frames: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        apart=(25.0 if r < 4 else 12.0 if r < 7 else 6.0 if r < 10
               else 4.0 if r < 13 else max(0.5, 3.0 * 0.88 ** (r - 13))),
        lengths=r >= 4,
        mirrored=r >= 7,
        frames=r >= 10)


class Puzzle(NamedTuple):
    level: Grade
    slopes: List[float]          # degrees above level, 0..90
    signs: List[int]             # +1 climbs to the right
    lengths: List[float]
    frames: List[float]          # each frame's tilt, degrees
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    return p.slopes.index(max(p.slopes))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    low = draw.uniform(15, 80 - level.apart)
    answer = S.slot(seed, 2)
    slopes = [low, low]
    slopes[answer] = low + level.apart
    signs = [1, 1]
    if level.mirrored:
        signs = [1, -1] if draw.random() < 0.5 else [-1, 1]
    lengths = [draw.uniform(0.25, 0.45) if level.lengths else 0.4
               for _k in range(2)]
    # A frame tilted the line's own way makes it look less steep.
    frames = [0.0, 0.0]
    if level.frames:
        frames = [signs[k] * (-12.0 if k == answer else 12.0) for k in range(2)]
    return Puzzle(level, slopes, signs, lengths, frames, draw.random(),
                  draw.choice(S.PAPERS), _('Which line is the steeper?'),
                  (_('Left'), _('Right')), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    ink = S.hsv(p.hue, 0.6, 0.45)
    for k in range(2):
        cx, cy = S.W * (0.25 + 0.5 * k), 0.5
        if p.level.frames:
            a = math.radians(p.frames[k])
            pts = S.place([(-1, -1), (1, -1), (1, 1), (-1, 1)], cx, cy, 0.27, a)
            for i in range(4):
                u, v = pts[i], pts[(i + 1) % 4]
                out.append(S.line(u[0], u[1], v[0], v[1], 0.006,
                                  (150, 150, 160)))
        a = math.radians(p.slopes[k])
        dx = math.cos(a) * p.lengths[k] / 2 * p.signs[k]
        dy = math.sin(a) * p.lengths[k] / 2
        out.append(S.line(cx - dx, cy - dy, cx + dx, cy + dy, 0.01, ink))
        out.append(S.hit(k * S.W / 2 + 0.01, 0.03, S.W / 2 - 0.02, 0.94, k))
    return out
