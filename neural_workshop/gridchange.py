# -*- coding: utf-8 -*-
"""Grid Change: see what was done to a grid, and do it to another.

Two or three pairs of small coloured grids, a before and an after: the
same change made to each. Then a new grid, and candidates for what the
change makes of it. The change is one of a stock of plain operations
-- flip, turn, recolour, let fall, shift, fill holes, keep the largest
piece, frame, double, mirror out -- or, higher up, two or three of them
one after another.

Every operation (and every pair, and a sample of triples) is tried on
the examples, and a deal is kept only when everything that fits the
examples does the same to the new grid. So the examples always settle
the answer.

The ladder:

* rungs 1-3: one flip or turn, on grids of three and four; three
  candidates;
* rungs 4-6: recolouring, falling and shifting as well; four
  candidates;
* rungs 7-9: two operations, one after the other;
* rungs 10-12: operations on pieces: fill the holes, keep the largest,
  frame, double, mirror out;
* rungs 13-15: up to three operations; grids to seven;
* from rung 16: two examples instead of three, grids a cell bigger
  every three rungs to twelve, and up to six candidates, some one cell
  off.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Callable, List, NamedTuple, Optional, Tuple

from .i18n import _

Grid = Tuple[Tuple[int, ...], ...]
BLANK = 0
#: Cell colours, 0 the blank.
PALETTE = ((24, 26, 34), (230, 70, 60), (50, 120, 230), (250, 200, 40),
           (60, 180, 90), (170, 90, 210), (250, 140, 40), (90, 210, 220),
           (240, 120, 180), (150, 150, 150))


def flip_h(g: Grid) -> Grid:
    return tuple(tuple(reversed(r)) for r in g)


def flip_v(g: Grid) -> Grid:
    return tuple(reversed(g))


def turn(g: Grid) -> Grid:
    """A quarter turn clockwise."""
    return tuple(zip(*g[::-1]))


def turn2(g: Grid) -> Grid:
    return flip_v(flip_h(g))


def turn3(g: Grid) -> Grid:
    return turn(turn2(g))


def transpose(g: Grid) -> Grid:
    return tuple(zip(*g))


def fall(g: Grid) -> Grid:
    """Every coloured cell drops to the bottom of its column."""
    cols = list(zip(*g))
    out = []
    for c in cols:
        full = [x for x in c if x != BLANK]
        out.append((BLANK,) * (len(c) - len(full)) + tuple(full))
    return tuple(zip(*out))


def fall_left(g: Grid) -> Grid:
    out = []
    for r in g:
        full = [x for x in r if x != BLANK]
        out.append(tuple(full) + (BLANK,) * (len(r) - len(full)))
    return tuple(out)


def shift(g: Grid) -> Grid:
    """Everything one cell right, the last column round to the first."""
    return tuple(r[-1:] + r[:-1] for r in g)


def shift_up(g: Grid) -> Grid:
    return g[1:] + g[:1]


def _pieces(g: Grid):
    h, w = len(g), len(g[0])
    seen = set()
    out = []
    for i in range(h):
        for j in range(w):
            if g[i][j] == BLANK or (i, j) in seen:
                continue
            stack, piece = [(i, j)], []
            seen.add((i, j))
            while stack:
                a, b = stack.pop()
                piece.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen \
                            and g[x][y] != BLANK:
                        seen.add((x, y))
                        stack.append((x, y))
            out.append(piece)
    return out


def keep_largest(g: Grid) -> Grid:
    pieces = _pieces(g)
    if not pieces:
        return g
    big = max(len(p) for p in pieces)
    keep = set()
    for p in pieces:
        if len(p) == big:
            keep |= set(p)
    return tuple(tuple(x if (i, j) in keep else BLANK for j, x in enumerate(r))
                 for i, r in enumerate(g))


def fill_holes(g: Grid) -> Grid:
    """Blank cells shut in by colour take the colour around them (the
    commonest colour next to the hole)."""
    h, w = len(g), len(g[0])
    outside = set()
    stack = [(i, j) for i in range(h) for j in range(w)
             if (i in (0, h - 1) or j in (0, w - 1)) and g[i][j] == BLANK]
    outside.update(stack)
    while stack:
        a, b = stack.pop()
        for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = a + da, b + db
            if 0 <= x < h and 0 <= y < w and (x, y) not in outside \
                    and g[x][y] == BLANK:
                outside.add((x, y))
                stack.append((x, y))
    rows = [list(r) for r in g]
    for i in range(h):
        for j in range(w):
            if g[i][j] == BLANK and (i, j) not in outside:
                near = [g[x][y] for x, y in ((i + 1, j), (i - 1, j),
                                             (i, j + 1), (i, j - 1))
                        if 0 <= x < h and 0 <= y < w and g[x][y] != BLANK]
                rows[i][j] = max(set(near), key=near.count) if near else 9
    return tuple(tuple(r) for r in rows)


def frame(g: Grid) -> Grid:
    """A grey frame round the edge."""
    h, w = len(g), len(g[0])
    return tuple(tuple(9 if i in (0, h - 1) or j in (0, w - 1) else g[i][j]
                       for j in range(w)) for i in range(h))


def double(g: Grid) -> Grid:
    """Every cell becomes two by two."""
    return tuple(tuple(x for x in r for _k in (0, 1)) for r in g
                 for _k in (0, 1))


def mirror_out(g: Grid) -> Grid:
    """The grid with its mirror image added on the right."""
    return tuple(r + tuple(reversed(r)) for r in g)


def recolour(a: int, b: int) -> Callable[[Grid], Grid]:
    def op(g: Grid) -> Grid:
        return tuple(tuple(b if x == a else a if x == b else x for x in r)
                     for r in g)
    op.__name__ = 'swap_%d_%d' % (a, b)
    return op


GEOMETRY = (flip_h, flip_v, turn, turn2, turn3, transpose)
MOVES = (fall, fall_left, shift, shift_up)
PIECES = (fill_holes, keep_largest, frame, double, mirror_out)


class Grade(NamedTuple):
    rung: int
    size: Tuple[int, int]
    steps: Tuple[int, int]
    recolours: bool
    moves: bool
    pieces: bool
    examples: int
    candidates: int
    off_by_one: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        size=((3, 4) if r < 4 else (4, 5) if r < 10 else (4, 6) if r < 13
              else (5, 7) if r < 16 else (6, min(12, 7 + (r - 16) // 3))),
        steps=(1, 1) if r < 7 else (2, 2) if r < 13 else (2, 3),
        recolours=r >= 4,
        moves=r >= 4,
        pieces=r >= 10,
        examples=3 if r < 16 else 2,
        candidates=3 if r < 4 else 4 if r < 16 else min(6, 5 + (r - 16) // 6),
        off_by_one=r >= 16)


class Puzzle(NamedTuple):
    level: Grade
    pairs: List[Tuple[Grid, Grid]]
    test: Grid
    cards: List[Grid]
    steps: Tuple[str, ...]
    question: str
    choices: Tuple[str, ...]
    answer: int


def _ops(level: Grade, colours: List[int]) -> List[Callable]:
    ops = list(GEOMETRY)
    if level.moves:
        ops += list(MOVES)
    if level.recolours:
        ops += [recolour(a, b) for a in colours for b in colours if a < b]
    if level.pieces:
        ops += list(PIECES)
    return ops


def run(chain, g: Grid) -> Grid:
    for op in chain:
        g = op(g)
    return g


def _grid(level: Grade, draw: random.Random, colours: List[int],
          pieces: bool) -> Grid:
    h = draw.randint(*level.size)
    w = draw.randint(*level.size)
    if pieces and draw.random() < 0.7:
        g = [[BLANK] * w for _k in range(h)]
        for _k in range(draw.randint(2, 3)):
            c = draw.choice(colours)
            bh, bw = draw.randint(2, max(2, h // 2 + 1)), \
                draw.randint(2, max(2, w // 2 + 1))
            i, j = draw.randrange(h - bh + 1), draw.randrange(w - bw + 1)
            ring = draw.random() < 0.5 and bh >= 3 and bw >= 3
            for a in range(bh):
                for b in range(bw):
                    if ring and 0 < a < bh - 1 and 0 < b < bw - 1:
                        continue
                    g[i + a][j + b] = c
        return tuple(tuple(r) for r in g)
    fill = draw.uniform(0.3, 0.6)
    return tuple(tuple(draw.choice(colours) if draw.random() < fill
                       else BLANK for _j in range(w)) for _i in range(h))


def _fits(chain, pairs) -> bool:
    return all(run(chain, a) == b for a, b in pairs)


def colours_of(pairs, test) -> List[int]:
    seen = {x for a, b in pairs for g in (a, b) for r in g for x in r}
    seen |= {x for r in test for x in r}
    return sorted(seen - {BLANK, 9})


def outcomes(level: Grade, pairs, test) -> set:
    """What every chain of the rung's operations that the examples
    allow makes of *test* -- every chain, tried in full."""
    ops = _ops(level, colours_of(pairs, test))
    first, want = pairs[0]
    out = set()
    longest = level.steps[1]
    # Chains grow a step at a time; a chain is kept whole only when it
    # turns the first example right, and then checked on the rest.
    level_chains = [((), first)]
    for depth in range(1, longest + 1):
        grown = []
        for chain, g in level_chains:
            for op in ops:
                h = op(g)
                if len(h) > 24 or len(h[0]) > 24:
                    continue
                c = chain + (op,)
                if depth < longest:
                    grown.append((c, h))
                if h == want and all(run(c, a) == b for a, b in pairs[1:]):
                    out.add(run(c, test))
        level_chains = grown
    return out


def solve(p: Puzzle) -> Optional[int]:
    got = outcomes(p.level, p.pairs, p.test)
    if len(got) != 1:
        return None
    want = got.pop()
    hits = [k for k, c in enumerate(p.cards) if c == want]
    return hits[0] if len(hits) == 1 else None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(400):
        colours = draw.sample(range(1, 9), draw.randint(2, 3))
        ops = _ops(level, colours)
        k = draw.randint(*level.steps)
        chain = tuple(draw.choice(ops) for _j in range(k))
        pieces = any(op in PIECES for op in chain)
        pairs = []
        for _j in range(level.examples):
            a = _grid(level, draw, colours, pieces)
            pairs.append((a, run(chain, a)))
        if any(a == b for a, b in pairs):
            continue
        test = _grid(level, draw, colours, pieces)
        answer = run(chain, test)
        if answer == test or len(answer) > 14 or len(answer[0]) > 14:
            continue
        got = outcomes(level, pairs, test)
        if got != {answer}:
            continue
        wrong = []
        pool = [run((op,), test) for op in ops] + [test]
        pool += [run((op,), answer) for op in ops]
        draw.shuffle(pool)
        if level.off_by_one:
            for _j in range(2):
                rows = [list(r) for r in answer]
                i, j = draw.randrange(len(rows)), draw.randrange(len(rows[0]))
                rows[i][j] = draw.choice([c for c in colours + [BLANK]
                                          if c != rows[i][j]])
                pool.insert(0, tuple(tuple(r) for r in rows))
        for g in pool:
            if len(wrong) >= level.candidates - 1:
                break
            if g != answer and g not in wrong:
                wrong.append(g)
        if len(wrong) < level.candidates - 1:
            continue
        where = draw.randrange(level.candidates)
        wrong.insert(where, answer)
        return Puzzle(level, pairs, test, wrong,
                      tuple(op.__name__ for op in chain),
                      _('What does the change make of the new grid?'),
                      tuple(str(j + 1) for j in range(level.candidates)),
                      where)
    raise RuntimeError('no grid change for rung %d' % rung)
