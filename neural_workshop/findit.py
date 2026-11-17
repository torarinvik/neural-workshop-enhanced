# -*- coding: utf-8 -*-
"""Find It: is the target among them?

The target is shown above; below, a crowd of figures flashes up for a
moment and is covered. Was the target there?

Visual search, from the easy kind to the hard: a target that differs
from everything else in one way *pops out* however many there are; one
that shares its colour with some and its shape with others has to be
looked for, one by one; and one that differs only in which way it
points -- among others just like it, turned -- is the slowest of all.

The ladder:

* rungs 1-3: six figures; the target alone in its colour; four seconds;
* rungs 4-6: twelve; the target shares a colour with some and a shape
  with others; two and a half seconds;
* rungs 7-9: eighteen; a second and a half;
* rungs 10-12: the target differs only in how it is turned;
* from rung 13: two figures more every rung to sixty, the look shorter
  toward four tenths of a second, and the turns a step apart.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _

YES, NO = 0, 1


class Grade(NamedTuple):
    rung: int
    items: int
    kind: str            # 'feature', 'conjunction', 'turn'
    show: float
    near: bool           # turns one step (45 degrees) apart


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        items=(6 if r < 4 else 12 if r < 7 else 18 if r < 10 else 20
               if r < 13 else min(60, 22 + 2 * (r - 13))),
        kind='feature' if r < 4 else 'conjunction' if r < 10 else 'turn',
        show=(4.0 if r < 4 else 2.5 if r < 7 else 1.5 if r < 13
              else max(0.4, 1.2 - 0.05 * (r - 13))),
        near=r >= 13)


class Item(NamedTuple):
    glyph: G.Glyph
    x: float
    y: float


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    target: G.Glyph
    items: List[Item]
    present: bool
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    want = G.seen(p.look, p.target)
    return YES if any(G.seen(p.look, it.glyph) == want
                      for it in p.items) else NO


def _distractor(level: Grade, lk: G.Look, target: G.Glyph, draw) -> G.Glyph:
    if level.kind == 'feature':
        return target._replace(colour=(target.colour + 1) % len(lk.colours),
                               shape=draw.randrange(len(lk.shapes)))
    if level.kind == 'conjunction':
        if draw.random() < 0.5:
            return target._replace(shape=(target.shape + draw.randint(
                1, len(lk.shapes) - 1)) % len(lk.shapes))
        return target._replace(colour=(target.colour + draw.randint(
            1, len(lk.colours) - 1)) % len(lk.colours))
    step = draw.choice((1, 7)) if level.near else draw.choice((2, 4, 6))
    return target._replace(turn=(target.turn + step) % G.TURNS)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    lk = G.look(draw, shapes=4 if level.kind != 'turn' else 2, colours=3,
                oriented=level.kind == 'turn')
    # Each palette's first two colours are far apart: a target alone in
    # its colour should leap out.
    lk = lk._replace(colours=tuple(draw.choice(G.PALETTES)[:3]))
    target = G.Glyph(draw.randrange(len(lk.shapes)),
                     draw.randrange(len(lk.colours)), 1, 1,
                     draw.randrange(G.TURNS) if level.kind == 'turn' else 0,
                     0, -1)
    present = draw.random() < 0.5
    side = int((level.items * 1.5) ** 0.5) + 1
    cells = [((j + 0.5) / side, (i + 0.5) / side)
             for i in range(side) for j in range(side)]
    draw.shuffle(cells)
    items = []
    for k, (x, y) in enumerate(cells[:level.items]):
        g = target if present and k == 0 else \
            _distractor(level, lk, target, draw)
        jx, jy = draw.uniform(-0.2, 0.2) / side, draw.uniform(-0.2, 0.2) / side
        items.append(Item(g, x + jx, y + jy))
    draw.shuffle(items)
    p = Puzzle(level, lk, target, items, present, 0.2, level.show + 6.0,
               (), (), _('Was the target there?'), (_('Yes'), _('No')),
               YES if present else NO)
    assert solve(p) == p.answer
    return p
