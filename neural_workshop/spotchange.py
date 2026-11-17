# -*- coding: utf-8 -*-
"""Spot the Change: two pictures flicker; one thing differs. Where?

A picture of scattered figures, then the same picture with one thing
changed, then the first again, round and round -- with a blank flash
between them past the first rungs. Without the blank the change jumps
out; with it, the eye has nothing to catch, and finding the change
means checking figure by figure (change blindness). Answer by the part
of the picture it is in.

The ladder:

* rungs 1-3: four parts, a few figures; a figure vanishes; no blank;
* rungs 4-6: nine parts, ten or so figures, a blank between; a figure
  vanishes, changes colour or changes shape;
* rungs 7-9: any change -- moved, grown, turned -- and fewer seconds;
* rungs 10-12: sixteen parts, twenty figures;
* from rung 13: a figure more every rung, to forty; the pictures
  shorter, and the time to answer shorter, down to six seconds.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _


class Grade(NamedTuple):
    rung: int
    parts: int           # a side: 2, 3 or 4
    items: int
    changes: Tuple[str, ...]
    show: float
    blank: float
    limit: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    changes = ('gone',)
    if r >= 4:
        changes += ('colour', 'shape')
    if r >= 7:
        changes += ('move', 'size', 'turn')
    if r >= 16:
        changes = ('colour', 'move', 'size', 'turn')
    return Grade(
        rung=r,
        parts=2 if r < 4 else 3 if r < 10 else 4,
        items=(5 if r < 4 else 10 if r < 7 else 12 if r < 10 else 20
               if r < 13 else min(40, 20 + (r - 12))),
        changes=changes,
        show=0.6 if r < 7 else 0.45 if r < 13 else 0.35,
        blank=0.0 if r < 4 else 0.15,
        limit=(18.0 if r < 7 else 14.0 if r < 13
               else max(6.0, 12.0 - 0.3 * (r - 13))))


class Item(NamedTuple):
    glyph: G.Glyph
    x: float
    y: float


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    before: List[Item]
    after: List[Item]
    changed: int
    change: str
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def part_of(level: Grade, x: float, y: float) -> int:
    n = level.parts
    col = min(n - 1, int(x * n))
    row = min(n - 1, int((1 - y) * n))
    return row * n + col


def showing(p: Puzzle, t: float) -> Optional[List[Item]]:
    """What is on screen at *t*: the first picture, the second, or
    nothing (the blank)."""
    period = p.level.show + p.level.blank
    k, into = divmod(t, period)
    if into >= p.level.show:
        return None
    return p.before if int(k) % 2 == 0 else p.after


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.parts
    for _attempt in range(300):
        lk = G.look(draw, shapes=6, colours=5)
        # Spread the figures over a jittered grid: one in every part
        # first, the rest anywhere.
        side = n * max(1, int(round((level.items * 1.6) ** 0.5 / n + 0.5)))
        cells = [((j + 0.5) / side, (i + 0.5) / side)
                 for i in range(side) for j in range(side)]
        draw.shuffle(cells)
        spots = []
        for part in range(n * n):
            spots.append(next(c for c in cells
                              if part_of(level, *c) == part))
        rest = [c for c in cells if c not in spots]
        spots += rest[:max(0, level.items - len(spots))]
        cell = 1.0 / side
        items = []
        for x, y in spots:
            g = G.random_glyph(draw, lk, size=draw.choice((0, 1)))
            items.append(Item(g, x + draw.uniform(-0.2, 0.2) * cell,
                              y + draw.uniform(-0.2, 0.2) * cell))
        k = draw.randrange(len(items))
        change = draw.choice(level.changes)
        it = items[k]
        g = it.glyph
        after = list(items)
        if change == 'gone':
            after[k] = None
        elif change == 'colour':
            after[k] = it._replace(glyph=g._replace(colour=(g.colour + draw.randint(
                1, len(lk.colours) - 1)) % len(lk.colours)))
        elif change == 'shape':
            after[k] = it._replace(glyph=g._replace(shape=(g.shape + draw.randint(
                1, len(lk.shapes) - 1)) % len(lk.shapes)))
        elif change == 'size':
            after[k] = it._replace(glyph=g._replace(size=1 - g.size + 1
                                                    if g.size == 0 else 0))
        elif change == 'turn':
            if not G.oriented(lk, g):
                continue
            after[k] = it._replace(glyph=g._replace(turn=(g.turn + 2) % 8))
        else:
            dx = draw.choice((-1, 1)) * cell * 0.3
            after[k] = it._replace(x=it.x + dx)
            if part_of(level, after[k].x, after[k].y) != \
                    part_of(level, it.x, it.y):
                continue
        after = [a for a in after if a is not None]
        part = part_of(level, it.x, it.y)
        return Puzzle(level, lk, items, after, k, change, 0.3, level.limit,
                      (), (), _('Something changes. In which part?'),
                      tuple(str(j + 1) for j in range(n * n)), part)
    raise RuntimeError('no change for rung %d' % rung)
