# -*- coding: utf-8 -*-
"""Contour: where is the path?

A field of short strokes pointing every way. In one part of it some of
them line up end to end along a smooth path, a chain the eye joins into
a line. Which part holds the path?

The ladder:

* rungs 1-3: left or right; ten strokes dead in line, gently curved;
* rungs 4-6: nine, each a little off true;
* rungs 7-9: four quarters; eight strokes;
* rungs 10-12: more off true; a tighter curve;
* from rung 13: seven strokes, further off true every rung, to
  fifteen degrees.

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
REACH = 0.15         # how far apart two strokes of a chain may be
TOL = math.radians(30)
TURN = math.radians(40)


class Grade(NamedTuple):
    rung: int
    regions: int
    strokes: int
    jitter: float        # degrees off the path's own direction
    curve: float         # degrees the path may turn at each stroke


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        regions=2 if r < 7 else 4,
        strokes=10 if r < 4 else 9 if r < 7 else 8 if r < 13 else 7,
        jitter=(0.0 if r < 4 else 5.0 if r < 7 else 7.0 if r < 10
                else 10.0 if r < 13 else min(15.0, 11.0 + 0.4 * (r - 13))),
        curve=12.0 if r < 10 else 20.0)


class Stroke(NamedTuple):
    x: float
    y: float
    angle: float


class Puzzle(NamedTuple):
    level: Grade
    strokes: List[Stroke]
    path: Tuple[int, ...]        # which strokes are the path
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


def _off(a: float, b: float) -> float:
    d = (a - b) % math.pi
    return min(d, math.pi - d)


def chain(strokes: List[Stroke]) -> List[int]:
    """The longest run of strokes lying end to end along a smooth line."""
    n = len(strokes)
    links = [[] for _k in range(n)]
    for i in range(n):
        a = strokes[i]
        for j in range(i + 1, n):
            b = strokes[j]
            if abs(a.x - b.x) > REACH or abs(a.y - b.y) > REACH:
                continue
            if math.hypot(a.x - b.x, a.y - b.y) > REACH:
                continue
            th = math.atan2(b.y - a.y, b.x - a.x)
            if _off(a.angle, th) < TOL and _off(b.angle, th) < TOL:
                links[i].append((j, th))
                links[j].append((i, th + math.pi))
    best: List[int] = []

    def walk(run, heading):
        nonlocal best
        if len(run) > len(best):
            best = list(run)
        for j, th in links[run[-1]]:
            if j in run:
                continue
            turn = abs((th - heading + math.pi) % (2 * math.pi) - math.pi)
            if turn <= TURN:
                run.append(j)
                walk(run, th)
                run.pop()

    for i in range(n):
        for j, th in links[i]:
            walk([i, j], th)
    return best


def solve(p: Puzzle) -> Optional[int]:
    run = chain(p.strokes)
    if len(run) < 3:
        return None
    x = sum(p.strokes[k].x for k in run) / len(run)
    y = sum(p.strokes[k].y for k in run) / len(run)
    return region(p.level, x, y)


def _box(level: Grade, k: int) -> Tuple[float, float, float, float]:
    half = S.W / 2
    if level.regions == 2:
        return (k * half, 0.0, half, 1.0)
    return ((k % 2) * half, 0.5 if k < 2 else 0.0, half, 0.5)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, level.regions)
    bx, by, bw, bh = _box(level, answer)
    names = (_('Left'), _('Right')) if level.regions == 2 else \
        (_('Top left'), _('Top right'), _('Bottom left'), _('Bottom right'))
    for _attempt in range(400):
        # The path first, wholly inside its part.
        pts = [(draw.uniform(bx + 0.06, bx + bw - 0.06),
                draw.uniform(by + 0.06, by + bh - 0.06))]
        heading = draw.uniform(0, 2 * math.pi)
        heads = []
        bend = draw.choice((-1, 1))
        for _k in range(level.strokes - 1):
            heading += bend * math.radians(draw.uniform(0.3, 1.0) * level.curve)
            heads.append(heading)
            pts.append((pts[-1][0] + math.cos(heading) * 0.095,
                        pts[-1][1] + math.sin(heading) * 0.095))
        if not all(bx + 0.05 < x < bx + bw - 0.05
                   and by + 0.05 < y < by + bh - 0.05 for x, y in pts):
            continue
        strokes = []
        for k, (x, y) in enumerate(pts):
            a = heads[min(k, len(heads) - 1)] if k == 0 else \
                heads[k - 1] if k == len(pts) - 1 else \
                (heads[k - 1] + heads[k]) / 2
            a += math.radians(draw.uniform(-level.jitter, level.jitter))
            strokes.append(Stroke(x, y, a % math.pi))
        path = tuple(range(len(strokes)))
        for cx in range(COLS):
            for cy in range(ROWS):
                x = (cx + 0.5) * CELL + draw.uniform(-0.025, 0.025)
                y = (cy + 0.5) * CELL + draw.uniform(-0.025, 0.025)
                if min(math.hypot(x - q[0], y - q[1]) for q in pts) < 0.078:
                    continue
                strokes.append(Stroke(x, y, draw.uniform(0, math.pi)))
        p = Puzzle(level, strokes, path, draw.random(), draw.choice(S.PAPERS),
                   _('Which part holds the path?'), names, answer)
        run = chain(strokes)
        # The path must be the longest chain there is, by a clear two.
        if solve(p) == answer and len(set(run) & set(path)) >= len(path) - 1:
            return p
    raise RuntimeError('no field for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    ink = S.hsv(p.hue, 0.5, 0.35)
    out = []
    grid = (190, 190, 200)
    out.append(S.line(S.W / 2, 0.0, S.W / 2, 1.0, 0.003, grid))
    if p.level.regions == 4:
        out.append(S.line(0.0, 0.5, S.W, 0.5, 0.003, grid))
    shown = set(p.path) if judged else ()
    for k, s in enumerate(p.strokes):
        dx, dy = math.cos(s.angle) * 0.03, math.sin(s.angle) * 0.03
        out.append(S.line(s.x - dx, s.y - dy, s.x + dx, s.y + dy, 0.007,
                          (215, 60, 60) if k in shown else ink))
    for k in range(p.level.regions):
        x, y, w, h = _box(p.level, k)
        out.append(S.hit(x + 0.005, y + 0.005, w - 0.01, h - 0.01, k))
    return out
