# -*- coding: utf-8 -*-
"""Polyominoes: shapes made of grid squares, turned, flipped and fitted.

Tangram and Will It Fit? both ask whether pieces go into a shape. On a
grid that question has an exact answer, which is why both are built on
squares; they are drawn as solid shapes, not as squares.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import FrozenSet, List, Sequence, Tuple

Cell = Tuple[int, int]
Shape = FrozenSet[Cell]


def normal(cells) -> Shape:
    """*cells* moved so the least row and column are 0."""
    cells = list(cells)
    r0 = min(r for r, _c in cells)
    c0 = min(c for _r, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def turn(s: Shape) -> Shape:
    """A quarter turn."""
    return normal((c, -r) for r, c in s)


def mirror(s: Shape) -> Shape:
    return normal((r, -c) for r, c in s)


def turns(s: Shape) -> List[Shape]:
    out = []
    for _k in range(4):
        if s not in out:
            out.append(s)
        s = turn(s)
    return out


def poses(s: Shape, flips: bool = True) -> List[Shape]:
    out = turns(s)
    if flips:
        for m in turns(mirror(s)):
            if m not in out:
                out.append(m)
    return out


def canon(s: Shape, flips: bool = True) -> Tuple[Cell, ...]:
    return min(tuple(sorted(p)) for p in poses(s, flips))


def grow(size: int, draw: random.Random) -> Shape:
    cells = {(0, 0)}
    while len(cells) < size:
        r, c = draw.choice(sorted(cells))
        dr, dc = draw.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        cells.add((r + dr, c + dc))
    return normal(cells)


def size_of(s: Shape) -> Tuple[int, int]:
    return (max(r for r, _c in s) + 1, max(c for _r, c in s) + 1)


def fits_in(piece: Shape, hole: Shape, flips: bool) -> bool:
    """Whether *piece*, turned (and flipped, if allowed) and moved,
    lies wholly inside *hole*."""
    for p in poses(piece, flips):
        for hr, hc in hole:
            for pr, pc in p:
                dr, dc = hr - pr, hc - pc
                if all((r + dr, c + dc) in hole for r, c in p):
                    return True
    return False


def tile(region: Shape, pieces: Sequence[Shape], flips: bool = True,
         limit: int = 200000) -> bool:
    """Whether *pieces* cover *region* exactly, each used once."""
    if sum(len(p) for p in pieces) != len(region):
        return False
    options = [poses(p, flips) for p in pieces]
    order = sorted(region)
    left = set(region)
    used = [False] * len(pieces)
    budget = [limit]

    def go() -> bool:
        if not left:
            return True
        budget[0] -= 1
        if budget[0] < 0:
            return False
        first = min(left)
        for k, opts in enumerate(options):
            if used[k]:
                continue
            for p in opts:
                # Anchor the pose's first cell (in reading order) on *first*.
                ar, ac = min(p)
                dr, dc = first[0] - ar, first[1] - ac
                cells = [(r + dr, c + dc) for r, c in p]
                if all(x in left for x in cells):
                    used[k] = True
                    for x in cells:
                        left.discard(x)
                    if go():
                        return True
                    used[k] = False
                    left.update(cells)
        return False

    del order
    return go()


def outline(s: Shape) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """The edges between a cell of *s* and a cell not in it, as
    segments in cell units (x right, y down)."""
    out = []
    for r, c in s:
        if (r - 1, c) not in s:
            out.append(((c, r), (c + 1, r)))
        if (r + 1, c) not in s:
            out.append(((c, r + 1), (c + 1, r + 1)))
        if (r, c - 1) not in s:
            out.append(((c, r), (c, r + 1)))
        if (r, c + 1) not in s:
            out.append(((c + 1, r), (c + 1, r + 1)))
    return out
