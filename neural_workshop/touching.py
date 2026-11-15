# -*- coding: utf-8 -*-
"""Touching?: do the shapes touch, overlap, or stand apart?

Two outlined shapes on a card. Apart, there is a clear gap of paper
between them; touching, their outlines meet at one point; overlapping,
one runs into the other. A person sees it at once; a model that reads
pictures as a bag of parts often cannot.

Exactly touching is exact: the gap is computed so the outlines' centre
lines meet. Apart and overlapping are never less than a small, visible
margin either way.

The ladder:

* rungs 1-3: two circles the same size, wide gaps and deep overlaps;
* rungs 4-6: different sizes, narrower margins;
* rungs 7-9: squares and circles, turned;
* rungs 10-12: how many pairs touch, among three to four circles;
* rungs 13-15: thick outlines and filled shapes, thin margins;
* from rung 16: more shapes and thinner margins every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

APART, TOUCHING, OVERLAPPING = 0, 1, 2
WORLD = 100.0            # the card is WORLD wide, 0.62 * WORLD tall


class Grade(NamedTuple):
    rung: int
    sizes: bool          # shapes of different sizes
    squares: bool        # squares as well as circles
    count: int           # 0: one pair asked about; else shapes to count among
    margin: float        # least gap or overlap, as a share of WORLD
    thick: bool          # thick outlines, or filled shapes


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        sizes=r >= 4,
        squares=7 <= r < 10 or r >= 13,
        count=(0 if r < 10 else 3 + (r % 2) if r < 16
               else min(6, 4 + (r - 16) // 3)),
        margin=(6.0 if r < 4 else 3.5 if r < 7 else 2.5 if r < 13
                else max(1.2, 2.0 - 0.05 * (r - 13))),
        thick=r >= 13)


class Shape(NamedTuple):
    kind: str            # 'circle' or 'square'
    x: float
    y: float
    r: float             # radius, or half side
    turn: float          # radians, squares only
    filled: bool


class Puzzle(NamedTuple):
    level: Grade
    shapes: List[Shape]
    question: str
    choices: Tuple[str, ...]
    answer: int


def _square_pts(s: Shape) -> List[Tuple[float, float]]:
    c, d = math.cos(s.turn), math.sin(s.turn)
    return [(s.x + s.r * (u * c - v * d), s.y + s.r * (u * d + v * c))
            for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _seg_dist(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) /
                     (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _inside_square(p, s: Shape) -> bool:
    c, d = math.cos(-s.turn), math.sin(-s.turn)
    u = (p[0] - s.x) * c - (p[1] - s.y) * d
    v = (p[0] - s.x) * d + (p[1] - s.y) * c
    return abs(u) <= s.r and abs(v) <= s.r


def gap(a: Shape, b: Shape) -> float:
    """Signed distance between the shapes: positive apart, zero
    touching, negative overlapping (how deep)."""
    if a.kind == 'circle' and b.kind == 'circle':
        return math.hypot(a.x - b.x, a.y - b.y) - a.r - b.r
    if a.kind == 'square' and b.kind == 'circle':
        a, b = b, a
    if a.kind == 'circle' and b.kind == 'square':
        pts = _square_pts(b)
        edge = min(_seg_dist((a.x, a.y), pts[k], pts[(k + 1) % 4])
                   for k in range(4))
        if _inside_square((a.x, a.y), b):
            return -(edge + a.r)
        return edge - a.r
    # Two squares: sample the outlines.
    pa, pb = _square_pts(a), _square_pts(b)
    best = float('inf')
    for k in range(4):
        for q in pb:
            best = min(best, _seg_dist(q, pa[k], pa[(k + 1) % 4]))
        for q in pa:
            best = min(best, _seg_dist(q, pb[k], pb[(k + 1) % 4]))
    deep = any(_inside_square(q, b) for q in pa) or \
        any(_inside_square(q, a) for q in pb) or \
        any(_cross(pa[i], pa[(i + 1) % 4], pb[j], pb[(j + 1) % 4])
            for i in range(4) for j in range(4))
    return -best if deep else best


def _cross(a, b, c, d) -> bool:
    """Whether segments ab and cd properly cross."""
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = side(c, d, a), side(c, d, b)
    d3, d4 = side(a, b, c), side(a, b, d)
    return d1 * d2 < -1e-9 and d3 * d4 < -1e-9


def kind_of(g: float, margin: float) -> int:
    if abs(g) < 1e-6:
        return TOUCHING
    return APART if g > 0 else OVERLAPPING


def _place_to(a: Shape, b: Shape, want: float, ang: float) -> Shape:
    """Move *b* along direction *ang* from *a* until the signed gap is
    *want* (bisection: gap grows with distance)."""
    lo, hi = 0.0, WORLD
    for _k in range(80):
        mid = (lo + hi) / 2
        c = b._replace(x=a.x + mid * math.cos(ang), y=a.y + mid * math.sin(ang))
        if gap(a, c) < want:
            lo = mid
        else:
            hi = mid
    return b._replace(x=a.x + hi * math.cos(ang), y=a.y + hi * math.sin(ang))


def _fits(s: Shape) -> bool:
    reach = s.r * (1.42 if s.kind == 'square' else 1.0)
    return reach + 3 < s.x < WORLD - reach - 3 and \
        reach + 3 < s.y < WORLD * 0.62 - reach - 3


def _shape(level: Grade, draw: random.Random) -> Shape:
    kind = 'square' if level.squares and draw.random() < 0.5 else 'circle'
    r = draw.uniform(8, 14) if level.sizes else 11.0
    if level.count:
        r *= 0.7
    return Shape(kind, WORLD / 2, WORLD * 0.31, r, draw.uniform(0, 1.6),
                 level.thick and draw.random() < 0.4)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    m = level.margin
    for _attempt in range(400):
        if not level.count:
            want = draw.choice((APART, TOUCHING, OVERLAPPING))
            a = _shape(level, draw)
            b = _shape(level, draw)
            ang = draw.uniform(0, 2 * math.pi)
            amount = {APART: draw.uniform(m, 3 * m), TOUCHING: 0.0,
                      OVERLAPPING: -draw.uniform(m, 3 * m)}[want]
            b = _place_to(a, b, amount, ang)
            shift = (WORLD / 2 - (a.x + b.x) / 2, WORLD * 0.31 -
                     (a.y + b.y) / 2)
            a = a._replace(x=a.x + shift[0], y=a.y + shift[1])
            b = b._replace(x=b.x + shift[0], y=b.y + shift[1])
            if not (_fits(a) and _fits(b)):
                continue
            g = gap(a, b)
            got = TOUCHING if abs(g) < 1e-3 else APART if g > 0 \
                else OVERLAPPING
            if got != want:
                continue
            return Puzzle(level, [a, b], _('Do the two shapes touch?'),
                          (_('Apart'), _('Touching'), _('Overlapping')),
                          want)
        # Count the touching pairs among several shapes.
        n = level.count
        shapes = [_shape(level, draw)._replace(
            x=draw.uniform(15, WORLD - 15), y=draw.uniform(12, 50))]
        pairs = 0
        ok = True
        for _k in range(n - 1):
            s = _shape(level, draw)
            base = draw.choice(shapes)
            roll = draw.random()
            amount = 0.0 if roll < 0.45 else draw.uniform(m, 3 * m) \
                if roll < 0.8 else -draw.uniform(m, 2.5 * m)
            s = _place_to(base, s, amount, draw.uniform(0, 2 * math.pi))
            if not _fits(s):
                ok = False
                break
            shapes.append(s)
        if not ok:
            continue
        # Every pair must be clearly one of the three.
        for i in range(n):
            for j in range(i):
                g = gap(shapes[i], shapes[j])
                if abs(g) < 1e-3:
                    pairs += 1
                elif abs(g) < m * 0.95:
                    ok = False
        if not ok or pairs > 5:
            continue
        return Puzzle(level, shapes, _('How many pairs of shapes touch '
                                       '(just touch, not overlap)?'),
                      tuple(str(k) for k in range(6)), pairs)
    raise RuntimeError('no Touching? puzzle for rung %d' % rung)
