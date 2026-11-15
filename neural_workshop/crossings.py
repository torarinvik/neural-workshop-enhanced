# -*- coding: utf-8 -*-
"""Crossings: how many times does the red line cross the blue?

Two lines wander over a card and cross some number of times. Counting
them is a matter of following one line along and ticking off each time
the other passes over it -- easy, if slow, for a person; models that
look at a picture as a whole are famously bad at it.

Every crossing is a clean one: lines meet at a fair angle, crossings
stand apart from one another, and away from its crossings a line never
grazes the other.

The ladder:

* rungs 1-3: two bent lines, up to two crossings;
* rungs 4-6: more bends, up to three;
* rungs 7-9: smooth curves, up to four;
* rungs 10-12: a green line crosses both as a decoy;
* rungs 13-15: up to five, at shallower angles;
* from rung 16: more decoys and up to six.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

W, H = 100.0, 62.0
Point = Tuple[float, float]


class Grade(NamedTuple):
    rung: int
    bends: int           # corner points along each line
    smooth: bool
    most: int            # the most crossings asked about
    decoys: int
    angle: float         # least crossing angle, degrees


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        bends=2 if r < 4 else 3 if r < 7 else 4 if r < 13 else 5,
        smooth=r >= 7,
        most=2 if r < 4 else 3 if r < 7 else 4 if r < 13 else 5 if r < 16
        else 6,
        decoys=0 if r < 10 else 1 if r < 16 else min(3, 2 + (r - 16) // 4),
        angle=30.0 if r < 13 else 18.0)


class Puzzle(NamedTuple):
    level: Grade
    red: List[Point]
    blue: List[Point]
    decoys: List[List[Point]]
    crossings: List[Point]
    question: str
    choices: Tuple[str, ...]
    answer: int


def _spline(ctrl: List[Point], per: int = 12) -> List[Point]:
    pts = [ctrl[0]] + ctrl + [ctrl[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t +
                                    (2 * p0[j] - 5 * p1[j] + 4 * p2[j] -
                                     p3[j]) * t2 +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j])
                                    * t3) for j in range(2)))
    out.append(ctrl[-1])
    return out


def _line(level: Grade, draw: random.Random) -> List[Point]:
    n = level.bends + 2
    side = draw.random() < 0.5
    pts = []
    for k in range(n):
        u = 6 + (W - 12) * k / (n - 1)
        v = draw.uniform(6, H - 6)
        pts.append((u, v) if side else (v / H * W * 0.98 + 1,
                                        u / W * H * 0.98 + 0.6))
    if draw.random() < 0.5:
        pts.reverse()
    return _spline(pts) if level.smooth else pts


def _hit(a, b, c, d) -> Optional[Tuple[Point, float]]:
    """Where segments ab and cd cross, and the angle between them."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if not (0 <= t < 1 and 0 <= u < 1):
        return None
    ang = abs(math.degrees(math.atan2(abs(den), r[0] * s[0] + r[1] * s[1])))
    return (a[0] + t * r[0], a[1] + t * r[1]), min(ang, 180 - ang)


def crossings(p: List[Point], q: List[Point]) -> List[Tuple[Point, float]]:
    out = []
    for i in range(len(p) - 1):
        for j in range(len(q) - 1):
            h = _hit(p[i], p[i + 1], q[j], q[j + 1])
            if h is not None:
                out.append(h)
    return out


def _clean(p, q, level: Grade, hits) -> bool:
    """Crossings at fair angles and apart; elsewhere no grazing."""
    if any(ang < level.angle for _pt, ang in hits):
        return False
    pts = [pt for pt, _a in hits]
    for i in range(len(pts)):
        for j in range(i):
            if math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) < 7:
                return False
    for a in p[::2]:
        if any(math.hypot(a[0] - c[0], a[1] - c[1]) < 6 for c in pts):
            continue
        for b in q:
            if math.hypot(a[0] - b[0], a[1] - b[1]) < 2.5:
                return False
    return True


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    want = draw.randint(0, level.most)
    for _attempt in range(3000):
        red, blue = _line(level, draw), _line(level, draw)
        hits = crossings(red, blue)
        if len(hits) != want or not _clean(red, blue, level, hits):
            continue
        decoys = []
        for _k in range(level.decoys):
            for _try in range(50):
                g = _line(level, draw)
                hr, hb = crossings(g, red), crossings(g, blue)
                if hr and hb and _clean(g, red, level, hr) and \
                        _clean(g, blue, level, hb):
                    decoys.append(g)
                    break
        if len(decoys) < level.decoys:
            continue
        return Puzzle(level, red, blue, decoys, [pt for pt, _a in hits],
                      _('How many times does the red line cross the blue '
                        'line?'),
                      tuple(str(k) for k in range(level.most + 1)), want)
    raise RuntimeError('no Crossings puzzle for rung %d' % rung)
