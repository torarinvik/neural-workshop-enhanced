# -*- coding: utf-8 -*-
"""Triples: three cards whose every property is all alike or all unlike.

Cards differ in colour, shape, number and fill, each one of three ways.
Three cards make a **triple** when, property by property, they are all
the same or all different -- three reds, or a red, a blue and a gold;
never two reds and a blue. Two cards fix the third that would complete
them, so the question is first which card does, then how many triples a
table holds.

The ladder:

* rungs 1-3: two properties vary (the rest are alike everywhere); which
  of two, then three, cards completes the pair;
* rungs 4-6: three properties; four candidates;
* rungs 7-9: all four; the wrong candidates each one property off;
* rungs 10-12: how many triples are on a table of six;
* from rung 13: a table of seven, and a card more every two rungs, to
  twelve.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from itertools import combinations
from typing import List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _

PROPS = ('colour', 'shape', 'count', 'fill')
Card = Tuple[int, int, int, int]     # each 0..2


class Grade(NamedTuple):
    rung: int
    vary: int
    candidates: int
    near: bool
    table: int           # 0: complete a pair; else how many triples here


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        vary=2 if r < 4 else 3 if r < 7 else 4,
        candidates=2 if r == 1 else 3 if r < 4 else 4,
        near=7 <= r < 10,
        table=0 if r < 10 else 6 if r < 13 else min(12, 7 + (r - 13) // 2))


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    pair: List[Card]
    cards: List[Card]          # candidates, or the table
    question: str
    choices: Tuple[str, ...]
    answer: int


def third(a: Card, b: Card) -> Card:
    return tuple(x if x == y else 3 - x - y for x, y in zip(a, b))


def is_triple(a: Card, b: Card, c: Card) -> bool:
    return all(len({x, y, z}) in (1, 3) for x, y, z in zip(a, b, c))


def count_triples(cards: List[Card]) -> int:
    return sum(1 for a, b, c in combinations(cards, 3) if is_triple(a, b, c))


def glyph(card: Card) -> G.Glyph:
    colour, shape, count, fill = card
    return G.Glyph(shape, colour, 1, count + 1, 0, fill, -1)


def solve(p: Puzzle) -> Optional[int]:
    if p.level.table:
        return count_triples(p.cards)
    hits = [k for k, c in enumerate(p.cards) if is_triple(p.pair[0],
                                                           p.pair[1], c)]
    return hits[0] if len(hits) == 1 else None


def _card(draw, vary: List[int], fixed: Card) -> Card:
    return tuple(draw.randrange(3) if k in vary else fixed[k]
                 for k in range(4))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    lk = G.look(draw, shapes=3, colours=3)
    vary = sorted(draw.sample(range(4), level.vary))
    fixed = tuple(draw.randrange(3) for _k in range(4))
    if level.table:
        top = 5 if level.table >= 9 else 3
        want = draw.randint(0, top)
        for _attempt in range(20000):
            cards = list({_card(draw, vary, fixed) for _k in range(
                level.table * 2)})[:level.table]
            if len(cards) == level.table and count_triples(cards) == want:
                return Puzzle(level, lk, [], cards,
                              _('How many triples are on the table?'),
                              tuple(str(k) for k in range(top + 1)), want)
            if _attempt % 200 == 199:
                want = draw.randint(0, top)
        raise RuntimeError('no table for rung %d' % rung)
    for _attempt in range(2000):
        a = _card(draw, vary, fixed)
        b = _card(draw, vary, fixed)
        if a == b:
            continue
        c = third(a, b)
        others: List[Card] = []
        for _k in range(200):
            if len(others) >= level.candidates - 1:
                break
            if level.near:
                k = draw.choice(vary)
                d = list(c)
                d[k] = (d[k] + draw.randint(1, 2)) % 3
                d = tuple(d)
            else:
                d = _card(draw, vary, fixed)
            if d in others or d in (a, b) or is_triple(a, b, d):
                continue
            others.append(d)
        if len(others) < level.candidates - 1:
            continue
        where = draw.randrange(level.candidates)
        others.insert(where, c)
        return Puzzle(level, lk, [a, b], others,
                      _('Which card makes a triple with the two?'),
                      tuple(str(k + 1) for k in range(level.candidates)),
                      where)
    raise RuntimeError('no triple for rung %d' % rung)
