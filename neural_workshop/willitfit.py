# -*- coding: utf-8 -*-
"""Will It Fit?: does the piece go into the hole?

A flat piece lies on the table and a hole is cut in a board. The piece
may be turned any way on the table -- but not turned over -- and slid
anywhere. Will it go into the hole? Higher up there are several holes:
which one does it go into?

The piece and the holes are made of squares, so the answer is exact,
and drawn as solid shapes. A hole that takes the piece has room to
spare; one that does not misses by as little as one square.

The ladder:

* rungs 1-3: a small piece the way up the hole is; the hole roomy or
  plainly too small;
* rungs 4-6: the piece shown turned;
* rungs 7-9: a hole that is the piece's mirror image -- it would fit
  turned over, which is not allowed;
* rungs 10-12: three holes; which one?
* from rung 13: four holes, bigger pieces (a square more every three
  rungs, to twelve), and the wrong holes a single square short.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import polyomino as P
from .i18n import _

YES, NO = 0, 1


class Grade(NamedTuple):
    rung: int
    size: int
    turned: bool
    mirrors: bool
    holes: int           # 1: will it fit; else which of these
    spare: int           # squares of room a fitting hole has


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        size=(3 if r < 4 else 4 if r < 7 else 5 if r < 13
              else min(12, 6 + (r - 13) // 3)),
        turned=r >= 4,
        mirrors=r >= 7,
        holes=1 if r < 10 else 3 if r < 13 else 4,
        spare=3 if r < 4 else 2 if r < 10 else 1)


class Puzzle(NamedTuple):
    level: Grade
    piece: P.Shape
    holes: List[P.Shape]
    hue: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> Optional[int]:
    fits = [k for k, h in enumerate(p.holes) if P.fits_in(p.piece, h, False)]
    if len(p.holes) == 1:
        return YES if fits else NO
    return fits[0] if len(fits) == 1 else None


def _roomy(piece: P.Shape, spare: int, draw) -> P.Shape:
    cells = set(piece)
    while len(cells) < len(piece) + spare:
        r, c = draw.choice(sorted(cells))
        dr, dc = draw.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        cells.add((r + dr, c + dc))
    return P.normal(cells)


def _tight(level: Grade, piece: P.Shape, draw) -> Optional[P.Shape]:
    """A hole of about the piece's size that it does not go into."""
    for _k in range(60):
        kind = draw.random()
        if level.mirrors and kind < 0.4:
            m = P.mirror(piece)
            if P.canon(m, False) == P.canon(piece, False):
                continue
            hole = _roomy(m, level.spare - 1 if level.spare > 1 else 0, draw)
        elif kind < 0.7:
            # The roomy hole with one of the piece's own squares taken.
            hole = set(_roomy(piece, level.spare, draw))
            hole.discard(draw.choice(sorted(hole)))
            if not hole:
                continue
            hole = P.normal(hole)
        else:
            hole = _roomy(P.grow(len(piece), draw), level.spare, draw)
        if len(hole) >= len(piece) and not P.fits_in(piece, hole, False):
            return hole
    return None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    hue = draw.choice(((230, 120, 60), (70, 140, 230), (90, 180, 110),
                       (200, 90, 170), (230, 180, 40)))
    for _attempt in range(400):
        piece = P.grow(level.size, draw)
        if level.mirrors and P.canon(P.mirror(piece), False) == \
                P.canon(piece, False):
            continue
        good = _roomy(piece, level.spare, draw)
        good = draw.choice(P.turns(good))
        shown = draw.choice(P.turns(piece)) if level.turned else piece
        if not level.turned:
            good = _roomy(piece, level.spare, draw)
        if level.holes == 1:
            want = draw.choice((YES, NO))
            hole = good if want == YES else _tight(level, piece, draw)
            if hole is None:
                continue
            if not level.turned and want == NO:
                pass
            p = Puzzle(level, shown, [hole], hue,
                       _('Will the piece go into the hole?'),
                       (_('Yes'), _('No')), want)
        else:
            holes = [good]
            for _k in range(level.holes - 1):
                h = _tight(level, piece, draw)
                if h is None:
                    break
                holes.append(draw.choice(P.turns(h)))
            if len(holes) < level.holes:
                continue
            where = random.Random(seed * 7 + 3).randrange(level.holes)
            holes.insert(where, holes.pop(0))
            p = Puzzle(level, shown, holes, hue,
                       _('Which hole does the piece go into?'),
                       tuple(str(k + 1) for k in range(level.holes)), where)
        if solve(p) != p.answer:
            continue
        return p
    raise RuntimeError('no fit for rung %d' % rung)
