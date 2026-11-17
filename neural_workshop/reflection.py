# -*- coding: utf-8 -*-
"""Reflection: which figure is the mirror image?

A figure and a mirror. Which of the figures on the right is what the
mirror shows? The others are the figure itself, the figure turned half
round, the figure mirrored the other way -- everything a mirror is
easily mistaken for -- and, higher up, a true reflection with one
stroke wrong.

The ladder:

* rungs 1-3: an upright mirror; the reflection or the figure itself;
* rungs 4-6: a mirror lying level; three figures;
* rungs 7-9: a mirror on the slant; four figures;
* rungs 10-12: a mirror at any angle;
* from rung 13: one of the others is a reflection with a stroke
  wrong; longer figures every few rungs.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

Path = Tuple[Tuple[float, float], ...]


class Grade(NamedTuple):
    rung: int
    figures: int
    mirrors: Tuple[float, ...]   # the mirror's angle, degrees; () for any
    strokes: int
    near: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        figures=2 if r < 4 else 3 if r < 7 else 4,
        mirrors=((90.0,) if r < 4 else (0.0, 90.0) if r < 7
                 else (45.0, 135.0) if r < 10 else ()),
        strokes=4 if r < 7 else 5 if r < 13 else min(8, 6 + (r - 13) // 4),
        near=r >= 13)


class Puzzle(NamedTuple):
    level: Grade
    figure: Path                 # about its own middle, reaching about 1.5
    mirror: float                # radians
    shown: List[Path]
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def mirrored(path: Path, angle: float) -> Path:
    """*path* reflected in a line through the origin at *angle*."""
    c, s = math.cos(2 * angle), math.sin(2 * angle)
    return tuple((x * c + y * s, x * s - y * c) for x, y in path)


def turned(path: Path, angle: float) -> Path:
    c, s = math.cos(angle), math.sin(angle)
    return tuple((x * c - y * s, x * s + y * c) for x, y in path)


def strokes(path: Path) -> frozenset:
    """The path as a set of strokes, whichever end it was drawn from."""
    pts = [(round(x, 3) + 0.0, round(y, 3) + 0.0) for x, y in path]
    return frozenset(frozenset((a, b)) for a, b in zip(pts, pts[1:]))


def solve(p: Puzzle) -> Optional[int]:
    want = strokes(mirrored(p.figure, p.mirror))
    hits = [k for k, s in enumerate(p.shown) if strokes(s) == want]
    return hits[0] if len(hits) == 1 else None


def _figure(n: int, draw: random.Random) -> Path:
    while True:
        at = (draw.randrange(4), draw.randrange(4))
        pts = [at]
        used = set()
        for _k in range(n):
            steps = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                     if (dx or dy) and 0 <= at[0] + dx < 4 and 0 <= at[1] + dy < 4
                     and (at[0] + dx, at[1] + dy) not in pts]
            if not steps:
                break
            dx, dy = draw.choice(steps)
            used.add((dx, dy))
            at = (at[0] + dx, at[1] + dy)
            pts.append(at)
        if len(pts) == n + 1 and len(used) >= 3:
            xs = [x for x, _y in pts]
            ys = [y for _x, y in pts]
            mx, my = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
            return tuple((x - mx, y - my) for x, y in pts)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.figures
    answer = S.slot(seed, n)
    for _attempt in range(500):
        fig = _figure(level.strokes, draw)
        angle = math.radians(draw.choice(level.mirrors) if level.mirrors
                             else draw.uniform(0, 180))
        right = mirrored(fig, angle)
        others = [fig, mirrored(fig, angle + math.pi / 2), turned(fig, math.pi)]
        if level.near:
            k = draw.randrange(1, len(right))
            bent = list(right)
            bent[k] = (bent[k][0] + draw.choice((-1, 1)) * math.cos(angle),
                       bent[k][1] + draw.choice((-1, 1)) * math.sin(angle))
            others[draw.randrange(3)] = tuple(bent)
        if n == 2:
            others = others[:1]
        else:
            draw.shuffle(others)
            others = others[:n - 1]
        shown = list(others)
        shown.insert(answer, right)
        if len({strokes(s) for s in shown}) < n:
            continue
        p = Puzzle(level, fig, angle, shown, draw.random(),
                   draw.choice(S.PAPERS),
                   _('Which figure is the mirror image?'),
                   tuple(str(k + 1) for k in range(n)), answer)
        if solve(p) == answer:
            return p
    raise RuntimeError('no figure for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    ink = S.hsv(p.hue, 0.6, 0.4)
    out = []
    cell = 0.065
    cx, cy = 0.5, 0.5
    c, s = math.cos(p.mirror), math.sin(p.mirror)
    nx, ny = -s, c
    # The mirror: a pale band with a bright edge.
    for k in range(-6, 6):
        out.append(S.line(cx + c * (k + 0.15) * 0.075, cy + s * (k + 0.15) * 0.075,
                          cx + c * (k + 0.85) * 0.075, cy + s * (k + 0.85) * 0.075,
                          0.008, (120, 150, 190)))
    off = 0.27
    here = [(cx - nx * off + x * cell, cy - ny * off + y * cell)
            for x, y in p.figure]
    out += S.polyline(here, 0.012, ink)
    there = (cx + nx * off, cy + ny * off)
    if judged:
        img = mirrored(p.figure, p.mirror)
        out += S.polyline([(there[0] + x * cell, there[1] + y * cell)
                           for x, y in img], 0.012, S.hsv(p.hue + 0.5, 0.7, 0.7))
    else:
        out.append(S.text(there[0], there[1], 0.09, '?', (150, 150, 160)))
    out.append(S.line(1.0, 0.03, 1.0, 0.97, 0.003, (190, 190, 200)))
    n = len(p.shown)
    for k, fig in enumerate(p.shown):
        if n == 2:
            bx, by, bw, bh = 1.0, 0.5 - 0.5 * k, 0.6, 0.5
        else:
            bx, by, bw, bh = 1.0 + 0.3 * (k % 2), 0.5 - 0.5 * (k // 2), 0.3, 0.5
        out += S.polyline([(bx + bw / 2 + x * cell, by + bh / 2 - 0.02 + y * cell)
                           for x, y in fig], 0.012, ink)
        out.append(S.text(bx + 0.04, by + bh - 0.05, 0.04, str(k + 1)))
        out.append(S.hit(bx + 0.006, by + 0.006, bw - 0.012, bh - 0.012, k))
    return out
