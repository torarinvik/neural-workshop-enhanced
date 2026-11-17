# -*- coding: utf-8 -*-
"""Tangram: which set of pieces makes this shape?

A silhouette, and a few sets of pieces beside it. Exactly one set can
be laid -- each piece turned or flipped as needed -- to cover the
silhouette with no gaps and no overlaps. The others have the same area
but cannot: one piece in them is a near miss.

The pieces are squares joined edge to edge, so whether a set covers the
shape is exact; they are drawn as solid shapes.

The ladder:

* rungs 1-3: two pieces of two or three squares; three sets;
* rungs 4-6: three pieces of three or four;
* rungs 7-9: three or four pieces of four, the wrong piece a near miss;
* rungs 10-12: four pieces of four or five; two pieces wrong, keeping
  the area;
* from rung 13: a piece more every three rungs, to eight, of up to six
  squares.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import polyomino as P
from .i18n import _


class Grade(NamedTuple):
    rung: int
    pieces: Tuple[int, int]
    size: Tuple[int, int]
    sets: int
    two_wrong: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        pieces=((2, 2) if r < 4 else (3, 3) if r < 7 else (3, 4) if r < 10
                else (4, 4) if r < 13 else (5, min(8, 5 + (r - 13) // 3))),
        size=((2, 3) if r < 4 else (3, 4) if r < 7 else (4, 4) if r < 10
              else (4, 5) if r < 13 else (4, 6)),
        sets=3 if r < 10 else 4,
        two_wrong=r >= 10)


class Puzzle(NamedTuple):
    level: Grade
    shape: P.Shape
    sets: List[List[P.Shape]]
    hues: List[Tuple[int, int, int]]
    question: str
    choices: Tuple[str, ...]
    answer: int


HUES = ((230, 90, 80), (70, 140, 230), (250, 190, 50), (80, 190, 110),
        (170, 100, 220), (240, 140, 60), (60, 190, 200), (230, 110, 170))


def solve(p: Puzzle) -> Optional[int]:
    ok = [k for k, s in enumerate(p.sets) if P.tile(p.shape, s)]
    return ok[0] if len(ok) == 1 else None


def _build(level: Grade, draw: random.Random):
    """Pieces laid edge to edge into a connected silhouette."""
    k = draw.randint(*level.pieces)
    pieces = [P.grow(draw.randint(*level.size), draw) for _j in range(k)]
    placed = set()
    for p in pieces:
        p = draw.choice(P.poses(p))
        if not placed:
            placed |= set(p)
            continue
        spots = []
        for r, c in placed:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                spots.append((r + dr, c + dc))
        draw.shuffle(spots)
        done = False
        for sr, sc in spots[:60]:
            for pr, pc in p:
                cells = {(r + sr - pr, c + sc - pc) for r, c in p}
                if not cells & placed:
                    placed |= cells
                    done = True
                    break
            if done:
                break
        if not done:
            return None, None
    return P.normal(placed), pieces


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(400):
        shape, pieces = _build(level, draw)
        if shape is None:
            continue
        h, w = P.size_of(shape)
        if max(h, w) > 12:
            continue
        wrong_sets = []
        for _k in range(80):
            if len(wrong_sets) >= level.sets - 1:
                break
            s = list(pieces)
            hits = draw.sample(range(len(s)), 2 if level.two_wrong and
                               len(s) > 2 and draw.random() < 0.5 else 1)
            if len(hits) == 1:
                s[hits[0]] = P.grow(len(s[hits[0]]), draw)
            else:
                a, b = hits
                total = len(s[a]) + len(s[b])
                na = draw.randint(max(2, total - 6), min(6, total - 2))
                s[a], s[b] = P.grow(na, draw), P.grow(total - na, draw)
            key = sorted(P.canon(x) for x in s)
            if key == sorted(P.canon(x) for x in pieces):
                continue
            if any(sorted(P.canon(x) for x in t) == key for t in wrong_sets):
                continue
            if P.tile(shape, s):
                continue
            wrong_sets.append(s)
        if len(wrong_sets) < level.sets - 1:
            continue
        sets = [[draw.choice(P.poses(x)) for x in s] for s in wrong_sets]
        where = random.Random(seed * 7 + 3).randrange(level.sets)
        sets.insert(where, [draw.choice(P.poses(x)) for x in pieces])
        for s in sets:
            draw.shuffle(s)
        p = Puzzle(level, shape, sets, draw.sample(HUES, len(HUES)),
                   _('Which set of pieces makes the shape?'),
                   tuple(str(k + 1) for k in range(level.sets)), where)
        if solve(p) != where:
            continue
        return p
    raise RuntimeError('no tangram for rung %d' % rung)
