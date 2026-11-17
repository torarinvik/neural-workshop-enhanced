# -*- coding: utf-8 -*-
"""Holds More: which container holds more?

Containers drawn side on -- a tall thin glass, a wide bowl, a vase that
swells and narrows -- each round about its middle, so what it holds is
its outline turned about its axis. Which holds the most? Higher up,
water stands in one and is poured into another: where does it come to?

The answers are exact (each outline is straight pieces, and each piece
turned is a slice of a cone), and the wrong ones are off by at least the
rung's margin. Tall and thin against short and wide is the old trap:
height is easy to see; width counts twice.

The ladder:

* rungs 1-3: two plain jars, one bigger every way;
* rungs 4-6: a tall thin one against a short wide one;
* rungs 7-9: cones, bowls and vases;
* rungs 10-12: three containers;
* rungs 13-15: poured: water in one, poured into another -- which mark
  does it reach?
* from rung 16: the margin narrows from a fifth to a twentieth, and up
  to four containers.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

#: An outline: (height, radius) from the bottom up, in centimetres.
Profile = Tuple[Tuple[float, float], ...]


class Grade(NamedTuple):
    rung: int
    count: int
    trap: bool           # tall-thin against short-wide
    shapes: bool         # cones, bowls, vases
    pour: bool
    margin: float        # least ratio between the right answer and the next


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        count=2 if r < 10 else 3 if r < 16 else min(4, 3 + (r - 16) // 4),
        trap=r >= 4,
        shapes=r >= 7,
        pour=r >= 13,
        margin=(1.8 if r < 4 else 1.35 if r < 7 else 1.25 if r < 13
                else max(1.05, 1.2 - 0.01 * (r - 13))))


class Puzzle(NamedTuple):
    level: Grade
    jars: List[Profile]
    poured: Optional[Tuple[int, int, float]]   # from, to, water height
    marks: List[float]                         # heights on the jar poured into
    hues: List[Tuple[int, int, int]]
    question: str
    choices: Tuple[str, ...]
    answer: int


def volume(p: Profile, upto: Optional[float] = None) -> float:
    """What *p* holds up to height *upto* (all of it if None)."""
    total = 0.0
    for (h0, r0), (h1, r1) in zip(p, p[1:]):
        if upto is not None and h0 >= upto:
            break
        if upto is not None and h1 > upto:
            t = (upto - h0) / (h1 - h0)
            r1 = r0 + (r1 - r0) * t
            h1 = upto
        total += math.pi * (h1 - h0) * (r0 * r0 + r0 * r1 + r1 * r1) / 3.0
    return total


def level_for(p: Profile, vol: float) -> float:
    """The height *vol* of water comes to in *p*."""
    lo, hi = 0.0, p[-1][0]
    for _k in range(60):
        mid = (lo + hi) / 2
        if volume(p, mid) < vol:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def solve(p: Puzzle) -> int:
    if p.poured is not None:
        a, b, h = p.poured
        want = level_for(p.jars[b], volume(p.jars[a], h))
        return min(range(len(p.marks)), key=lambda k: abs(p.marks[k] - want))
    vols = [volume(j) for j in p.jars]
    return vols.index(max(vols))


def _jar(level: Grade, draw: random.Random, tall: Optional[bool]) -> Profile:
    if tall is None:
        h, r = draw.uniform(6, 16), draw.uniform(2.5, 6)
    elif tall:
        h, r = draw.uniform(13, 18), draw.uniform(2, 3.4)
    else:
        h, r = draw.uniform(4, 7), draw.uniform(4.5, 7.5)
    kind = draw.choice(('jar', 'cone', 'bowl', 'vase', 'flute')) \
        if level.shapes else 'jar'
    if kind == 'jar':
        return ((0, r), (h, r))
    if kind == 'cone':
        return ((0, r * 0.35), (h, r * 1.3))
    if kind == 'flute':
        return ((0, r * 1.2), (h * 0.5, r * 0.8), (h, r * 0.7))
    if kind == 'bowl':
        return tuple((h * t, r * (0.35 + 0.95 * math.sin(t * math.pi / 2)))
                     for t in (0, 0.25, 0.5, 0.75, 1.0))
    return ((0, r * 0.6), (h * 0.35, r * 1.2), (h * 0.7, r * 0.75),
            (h, r * 0.55))


HUES = ((120, 180, 220), (230, 170, 120), (170, 210, 150), (220, 160, 200),
        (240, 210, 120))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    hues = draw.sample(HUES, len(HUES))
    if level.pour and draw.random() < 0.5:
        for _attempt in range(500):
            a, b = _jar(level, draw, None), _jar(level, draw, None)
            h = a[-1][0] * draw.uniform(0.4, 0.8)
            v = volume(a, h)
            if v > volume(b) * 0.92:
                continue
            want = level_for(b, v)
            top = b[-1][0]
            gap = top * (0.22 if level.rung < 16 else
                         max(0.06, 0.18 - 0.006 * (level.rung - 16)))
            where = draw.randrange(3)
            marks = [want + (k - where) * gap for k in range(3)]
            if marks[0] < top * 0.05 or marks[-1] > top * 0.97:
                continue
            p = Puzzle(level, [a, b], (0, 1, h), marks, hues,
                       _('Poured into the other, where will the water '
                         'come to?'), (_('Low'), _('Middle'), _('High')),
                       where)
            if solve(p) == where:
                return p
    for _attempt in range(2000):
        jars = []
        for k in range(level.count):
            tall = None if not level.trap else (k % 2 == 0)
            jars.append(_jar(level, draw, tall))
        draw.shuffle(jars)
        vols = sorted(volume(j) for j in jars)
        if vols[-1] < vols[-2] * level.margin or \
                vols[-1] > vols[-2] * level.margin * 1.6:
            continue
        if not level.trap and level.rung < 4:
            # The bigger one is bigger every way.
            big = max(jars, key=volume)
            if any(j is not big and (j[-1][0] > big[-1][0] or
                                     max(r for _h, r in j) >
                                     max(r for _h, r in big)) for j in jars):
                continue
        if level.trap and level.count == 2 and draw.random() < 0.6:
            # Most of the time the tall one is the smaller.
            tall = max(jars, key=lambda j: j[-1][0])
            if volume(tall) == vols[-1]:
                continue
        p = Puzzle(level, jars, None, [], hues,
                   _('Which holds the most?'),
                   tuple(str(k + 1) for k in range(level.count)), 0)
        p = p._replace(answer=solve(p))
        return p
    raise RuntimeError('no containers for rung %d' % rung)
