# -*- coding: utf-8 -*-
"""Symmetric?: is the pattern its own mirror image?

A pattern of coloured cells. Is it symmetric -- does folding it along
some line lay every cell on one of its own colour? The patterns that
are not are, past the first rungs, symmetric patterns with a few cells
spoiled, down to a single cell, and higher still that cell is swapped
with another, so even the colour counts give nothing away.

The cells are drawn several ways -- squares, dots, tiles -- and in
several palettes; the question is always the same.

The ladder:

* rungs 1-3: grids of four to six, folded down the middle only; the
  others plainly lopsided;
* rungs 4-6: folded across as well; the others three cells off;
* rungs 7-9: along either diagonal too; two cells off;
* rungs 10-12: grids of eight to ten; one cell off;
* rungs 13-15: or the question is whether it looks the same turned
  upside down;
* from rung 16: grids a cell bigger every two rungs, to twenty-four,
  four colours, and the spoilt cell swapped rather than recoloured.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

YES, NO = 0, 1
Grid = Tuple[Tuple[int, ...], ...]
PALETTES = (
    ((240, 240, 236), (40, 60, 120), (230, 90, 70), (250, 190, 50),
     (60, 160, 120)),
    ((250, 246, 240), (120, 40, 90), (40, 150, 170), (240, 140, 40),
     (90, 90, 90)),
    ((236, 244, 250), (30, 30, 40), (220, 60, 90), (60, 120, 220),
     (250, 210, 60)),
)
STYLES = ('squares', 'dots', 'tiles')


class Grade(NamedTuple):
    rung: int
    size: Tuple[int, int]
    axes: Tuple[str, ...]
    off: int             # cells spoilt; 0 for a plain random pattern
    turned: bool         # may ask about the half turn instead
    colours: int
    swap: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    axes = ('v',) if r < 4 else ('v', 'h') if r < 7 else ('v', 'h', 'd', 'a')
    return Grade(
        rung=r,
        size=((4, 6) if r < 10 else (8, 10) if r < 16
              else (10, min(24, 10 + (r - 16) // 2))),
        axes=axes,
        off=0 if r < 4 else 3 if r < 7 else 2 if r < 10 else 1,
        turned=r >= 13,
        colours=2 if r < 7 else 3 if r < 16 else 4,
        swap=r >= 16)


class Puzzle(NamedTuple):
    level: Grade
    grid: Grid
    kind: str            # 'mirror' or 'turn'
    palette: int
    style: str
    question: str
    choices: Tuple[str, ...]
    answer: int


def mirrored(g: Grid, axis: str) -> Grid:
    if axis == 'v':
        return tuple(tuple(reversed(r)) for r in g)
    if axis == 'h':
        return tuple(reversed(g))
    if axis == 'd':
        return tuple(zip(*g))
    if axis == 'a':
        return tuple(zip(*[tuple(reversed(r)) for r in reversed(g)]))
    raise ValueError(axis)


def half_turn(g: Grid) -> Grid:
    return tuple(tuple(reversed(r)) for r in reversed(g))


def symmetric(g: Grid, kind: str, axes) -> bool:
    if kind == 'turn':
        return half_turn(g) == g
    square = len(g) == len(g[0])
    return any(mirrored(g, a) == g for a in axes
               if a in 'vh' or square)


def solve(p: Puzzle) -> int:
    return YES if symmetric(p.grid, p.kind, p.level.axes) else NO


def _make(level: Grade, draw: random.Random, kind: str, axis: str,
          h: int, w: int) -> List[List[int]]:
    g = [[draw.randrange(level.colours) if draw.random() < 0.55 else 0
          for _j in range(w)] for _i in range(h)]
    g = [[min(x, level.colours - 1) for x in r] for r in g]
    for i in range(h):
        for j in range(w):
            if kind == 'turn':
                a, b = h - 1 - i, w - 1 - j
            elif axis == 'v':
                a, b = i, w - 1 - j
            elif axis == 'h':
                a, b = h - 1 - i, j
            elif axis == 'd':
                a, b = j, i
            else:
                a, b = w - 1 - j, h - 1 - i
            if (a, b) < (i, j):
                g[i][j] = g[a][b]
    return g


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    want = draw.choice((YES, NO))
    kind = 'turn' if level.turned and draw.random() < 0.4 else 'mirror'
    for _attempt in range(500):
        axis = draw.choice(level.axes)
        n = draw.randint(*level.size)
        h, w = (n, n) if axis in 'da' or kind == 'turn' and \
            draw.random() < 0.5 else (n, draw.randint(*level.size))
        if axis in 'da':
            h = w = n
        if want == NO and level.off == 0:
            g = [[draw.randrange(level.colours) for _j in range(w)]
                 for _i in range(h)]
        else:
            g = _make(level, draw, kind, axis, h, w)
            if want == NO:
                cells = [(i, j) for i in range(h) for j in range(w)]
                for _k in range(level.off):
                    i, j = draw.choice(cells)
                    if level.swap:
                        a, b = draw.choice(cells)
                        g[i][j], g[a][b] = g[a][b], g[i][j]
                    else:
                        g[i][j] = (g[i][j] + draw.randint(
                            1, level.colours - 1)) % level.colours
        grid = tuple(tuple(r) for r in g)
        if sum(x != 0 for r in grid for x in r) < len(grid) * len(grid[0]) // 4:
            continue
        if symmetric(grid, kind, level.axes) != (want == YES):
            continue
        if kind == 'turn' and want == NO and symmetric(
                grid, 'mirror', level.axes):
            continue
        q = (_('Does it look the same turned upside down?') if kind == 'turn'
             else _('Is the pattern mirror symmetric?'))
        return Puzzle(level, grid, kind, draw.randrange(len(PALETTES)),
                      draw.choice(STYLES), q, (_('Yes'), _('No')), want)
    raise RuntimeError('no pattern for rung %d' % rung)
