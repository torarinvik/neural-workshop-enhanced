# -*- coding: utf-8 -*-
"""Inside or Out?: is the dot inside the closed line?

One closed line that never crosses itself, and a dot. A glance answers
it for a blob; a winding labyrinth needs the line followed -- or the
dot's way out looked for. The question never changes, only how much
line there is to understand.

The line is the boundary of a region grown cell by cell on a hidden
grid, one cell wide in places, so it folds back on itself into
corridors and dead ends. The dot sits in the middle of a cell, so it is
never on the line.

The ladder:

* rungs 1-3: a round blob, the dot well inside or well out;
* rungs 4-6: a blob with deep fingers, the dot in a finger or a bay;
* rungs 7-9: a small labyrinth;
* rungs 10-12: a larger one;
* rungs 13-15: two dots: can one reach the other without crossing?;
* rungs 16-19: loose lines that do not close lie about as decoys;
* from rung 20: larger labyrinths every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Set, Tuple

from .i18n import _

Cell = Tuple[int, int]
Point = Tuple[float, float]


class Grade(NamedTuple):
    rung: int
    kind: str            # 'blob', 'fingers' or 'maze'
    size: int            # grid cells a side
    pair: bool           # two dots, same side or not
    decoys: int          # loose lines that do not close


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        kind='blob' if r < 4 else 'fingers' if r < 7 else 'maze',
        size=(26 if r < 7 else 9 if r < 10 else 13 if r < 13 else 15
              if r < 20 else min(31, 15 + 2 * (r - 19))),
        pair=13 <= r < 16 or (r >= 20 and r % 2 == 1),
        decoys=0 if r < 16 else 3 + (r - 16) // 2)


class Puzzle(NamedTuple):
    level: Grade
    size: int
    region: Set[Cell]
    loops: List[List[Point]]        # the closed line (one loop)
    decoys: List[List[Point]]       # loose lines
    dots: List[Point]
    question: str
    choices: Tuple[str, ...]
    answer: int


IN, OUT = 0, 1


def _blob(n: int, draw: random.Random, fingers: bool) -> Set[Cell]:
    c = (n - 1) / 2.0
    base = n * 0.34
    waves = [(draw.randint(2, 4), draw.uniform(0, 6.3), draw.uniform(0.05,
                                                                      0.15))]
    if fingers:
        waves.append((draw.randint(4, 6), draw.uniform(0, 6.3), 0.42))
    out = set()
    for x in range(n):
        for y in range(n):
            a = math.atan2(y - c, x - c)
            r = base * (1 + sum(amp * math.sin(k * a + ph)
                                for k, ph, amp in waves))
            if math.hypot(x - c, y - c) <= r:
                out.add((x, y))
    return out


def _maze(n: int, draw: random.Random) -> Set[Cell]:
    """A tree of one-cell corridors on the even cells, so the region is
    one piece with no holes and folds back on itself everywhere."""
    start = (2 * draw.randrange(n // 2), 2 * draw.randrange(n // 2))
    region = {start}
    frontier = [start]
    target = int(n * n * 0.42)
    while frontier and len(region) < target:
        cell = frontier[-1] if draw.random() < 0.75 else \
            draw.choice(frontier)
        x, y = cell
        steps = [(dx, dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
                 if 0 <= x + dx < n and 0 <= y + dy < n
                 and (x + dx, y + dy) not in region]
        if not steps:
            frontier.remove(cell)
            continue
        dx, dy = draw.choice(steps)
        region.add((x + dx // 2, y + dy // 2))
        region.add((x + dx, y + dy))
        frontier.append((x + dx, y + dy))
    return region


def _connected(region: Set[Cell]) -> bool:
    if not region:
        return False
    start = next(iter(region))
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if c in region and c not in seen:
                seen.add(c)
                todo.append(c)
    return len(seen) == len(region)


def _outside(region: Set[Cell], n: int) -> Set[Cell]:
    """Cells not in the region that reach the edge of a margin round it."""
    lo, hi = -1, n
    seen = {(lo, lo)}
    todo = [(lo, lo)]
    while todo:
        x, y = todo.pop()
        for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if lo <= c[0] <= hi and lo <= c[1] <= hi and c not in region \
                    and c not in seen:
                seen.add(c)
                todo.append(c)
    return seen


def boundary(region: Set[Cell]) -> List[List[Point]]:
    """The region's outline as closed loops of corner points."""
    edges = {}
    for x, y in region:
        for (ax, ay), (bx, by), (nx, ny) in (
                ((x, y), (x + 1, y), (x, y - 1)),
                ((x + 1, y), (x + 1, y + 1), (x + 1, y)),
                ((x + 1, y + 1), (x, y + 1), (x, y + 1)),
                ((x, y + 1), (x, y), (x - 1, y))):
            if (nx, ny) not in region:
                edges[(ax, ay)] = edges.get((ax, ay), []) + [(bx, by)]
    loops = []
    while edges:
        start = next(iter(edges))
        loop = [start]
        cur = start
        while True:
            nxt = edges[cur].pop()
            if not edges[cur]:
                del edges[cur]
            if nxt == start:
                break
            loop.append(nxt)
            cur = nxt
        loops.append([(float(a), float(b)) for a, b in loop])
    return loops


def _decoy(n: int, draw: random.Random) -> List[Point]:
    x, y = draw.uniform(0, n), draw.uniform(0, n)
    pts = [(x, y)]
    a = draw.uniform(0, 6.3)
    for _k in range(draw.randint(3, 6)):
        a += draw.uniform(-1.2, 1.2)
        x = max(0.0, min(n, x + math.cos(a) * draw.uniform(1, 3)))
        y = max(0.0, min(n, y + math.sin(a) * draw.uniform(1, 3)))
        pts.append((x, y))
    return pts


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.size
    for _attempt in range(200):
        if level.kind == 'maze':
            region = _maze(n, draw)
        else:
            region = _blob(n, draw, level.kind == 'fingers')
        if not _connected(region):
            continue
        out = _outside(region, n)
        holes = {(x, y) for x in range(n) for y in range(n)} - region - out
        if holes:
            continue                    # only one closed line, no islands
        loops = boundary(region)
        if len(loops) != 1:
            continue
        inner = [c for c in region]
        outer = [c for c in out if 0 <= c[0] < n and 0 <= c[1] < n]
        if not inner or not outer:
            continue
        # Hard spots: cells whose neighbours are mostly the other side.
        def tight(c, side):
            x, y = c
            return sum((x + dx, y + dy) not in side
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        if level.kind == 'blob':
            inner = [c for c in inner if tight(c, region) == 0]
            outer = [c for c in outer if tight(c, out) == 0]
        else:
            inner.sort(key=lambda c: -tight(c, region))
            outer.sort(key=lambda c: -tight(c, out))
            inner = inner[:max(3, len(inner) // 3)]
            outer = outer[:max(3, len(outer) // 3)]
        if not inner or not outer:
            continue
        decoys = [_decoy(n, draw) for _k in range(level.decoys)]
        if level.pair:
            same = draw.random() < 0.5
            a_in = draw.random() < 0.5
            first = draw.choice(inner if a_in else outer)
            pool = (inner if a_in else outer) if same else \
                (outer if a_in else inner)
            pool = [c for c in pool if abs(c[0] - first[0]) +
                    abs(c[1] - first[1]) > n // 3]
            if not pool:
                continue
            second = draw.choice(pool)
            dots = [(first[0] + 0.5, first[1] + 0.5),
                    (second[0] + 0.5, second[1] + 0.5)]
            return Puzzle(level, n, region, loops, decoys, dots,
                          _('Can the two dots meet without crossing the '
                            'line?'), (_('Yes'), _('No')),
                          0 if same else 1)
        inside = draw.random() < 0.5
        cell = draw.choice(inner if inside else outer)
        return Puzzle(level, n, region, loops, decoys,
                      [(cell[0] + 0.5, cell[1] + 0.5)],
                      _('Is the dot inside the closed line?'),
                      (_('Inside'), _('Outside')), IN if inside else OUT)
    raise RuntimeError('no Inside or Out? puzzle for rung %d' % rung)


def contains(loop: List[Point], p: Point) -> bool:
    """Even-odd test: a ray to the right crosses the line an odd number
    of times from inside."""
    x, y = p
    inside = False
    for (ax, ay), (bx, by) in zip(loop, loop[1:] + loop[:1]):
        if (ay > y) != (by > y):
            cross = ax + (y - ay) * (bx - ax) / (by - ay)
            if cross > x:
                inside = not inside
    return inside
