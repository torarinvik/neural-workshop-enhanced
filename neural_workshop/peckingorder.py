# -*- coding: utf-8 -*-
"""Pecking Order: who beats whom, from pairs.

Some creatures stand in an order nobody shows. The clues are pairs --
this one beats that one -- and the question is about a pair the clues
never mention together: who wins? Higher up, where does one creature
stand in the whole order?

Transitive inference: A beats B and B beats C, so A beats C. The clues
are always enough, and never more than the order needs at the low
rungs.

The ladder:

* rungs 1-3: three creatures, the clues in order down the page;
* rungs 4-6: four, the clues shuffled, the asked pair two steps apart
  or more;
* rungs 7-9: five, and a clue more than needed;
* rungs 10-12: six, and some clues read the other way -- "loses to";
* rungs 13-15: seven or eight, the pair far apart, more spare clues;
* from rung 16: which creature stands k-th, among all of them, with a
  creature more every three rungs, to twelve.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _

#: A clue: (winner, loser, said_backwards) by creature index.
Clue = Tuple[int, int, bool]


class Grade(NamedTuple):
    rung: int
    count: int
    shuffled: bool
    spare: int
    backwards: bool
    apart: int           # least steps between the asked pair
    place: bool          # ask a creature's place in the order


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        count=(3 if r < 4 else 4 if r < 7 else 5 if r < 10 else 6 if r < 13
               else 7 + (r % 2) if r < 16 else min(12, 6 + (r - 16) // 3)),
        shuffled=r >= 4,
        spare=0 if r < 7 else 1 if r < 13 else 2,
        backwards=r >= 10,
        apart=1 if r < 4 else 2 if r < 13 else 3,
        place=r >= 16)


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    creatures: List[G.Glyph]
    order: List[int]          # creature indices, best first
    clues: List[Clue]
    pair: Tuple[int, int]     # asked: who wins (two-way questions)
    rank: int                 # asked: who stands here (place questions)
    question: str
    choices: Tuple[str, ...]
    answer: int


def ranking(n: int, clues: List[Clue]) -> Optional[List[int]]:
    """The one order the clues allow, or None when they allow more."""
    beats = {k: set() for k in range(n)}
    for w, l, _b in clues:
        beats[w].add(l)
    indeg = {k: 0 for k in range(n)}
    for w in beats:
        for l in beats[w]:
            indeg[l] += 1
    order = []
    ready = [k for k in range(n) if indeg[k] == 0]
    while ready:
        if len(ready) > 1:
            return None
        k = ready.pop()
        order.append(k)
        for l in beats[k]:
            indeg[l] -= 1
            if indeg[l] == 0:
                ready.append(l)
    return order if len(order) == n else None


def solve(p: Puzzle) -> Optional[int]:
    order = ranking(len(p.creatures), p.clues)
    if order is None:
        return None
    if p.level.place:
        return order[p.rank]
    a, b = p.pair
    return 0 if order.index(a) < order.index(b) else 1


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.count
    lk = G.look(draw, shapes=min(12, max(6, n)), colours=6)
    kinds = [(s, c) for s in range(len(lk.shapes)) for c in range(len(lk.colours))]
    draw.shuffle(kinds)
    # No two creatures share a shape or a colour where there are enough.
    picked: List[Tuple[int, int]] = []
    for s, c in kinds:
        if len(picked) == n:
            break
        if any(s == ps for ps, _pc in picked) and len(picked) < len(lk.shapes):
            continue
        if any(c == pc for _ps, pc in picked) and len(picked) < len(lk.colours):
            continue
        picked.append((s, c))
    creatures = [G.Glyph(s, c, 1, 1, 0, 0, -1) for s, c in picked]
    order = list(range(n))
    draw.shuffle(order)
    clues: List[Clue] = [(order[k], order[k + 1], False) for k in range(n - 1)]
    for _k in range(level.spare):
        i, j = sorted(draw.sample(range(n), 2))
        if j - i >= 2:
            clues.append((order[i], order[j], False))
    if level.shuffled:
        draw.shuffle(clues)
    if level.backwards:
        clues = [(w, l, draw.random() < 0.4) for w, l, _b in clues]
    if level.place:
        rank = draw.randrange(n)
        names = tuple(str(k + 1) for k in range(n))
        p = Puzzle(level, lk, creatures, order, clues, (0, 0), rank,
                   _('Which one stands %s in the order?') % _ordinal(rank),
                   names, order[rank])
        return p
    gap = min(n - 1, draw.randint(level.apart, n - 1))
    i = draw.randrange(n - gap)
    a, b = order[i], order[i + gap]
    if draw.random() < 0.5:
        a, b = b, a
    answer = 0 if order.index(a) < order.index(b) else 1
    return Puzzle(level, lk, creatures, order, clues, (a, b), 0,
                  _('Who wins?'), (_('Left'), _('Right')), answer)


def _ordinal(k: int) -> str:
    words = (_('first'), _('second'), _('third'), _('fourth'), _('fifth'),
             _('sixth'), _('seventh'), _('eighth'), _('ninth'), _('tenth'),
             _('eleventh'), _('twelfth'))
    return words[k]
