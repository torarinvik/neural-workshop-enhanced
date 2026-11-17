# -*- coding: utf-8 -*-
"""Top Card: which card lies where in the pile?

Cards dropped one on another, each with a number. Where one card's edge
runs on unbroken across another, it lies over it; from that alone the
whole order of the pile can be read. Which card is on top? Higher up:
which is at the bottom, which is second from the top.

Every card lies partly over the one dropped before it, so the order is
always there to be read.

The ladder:

* rungs 1-3: three cards; which is on top?
* rungs 4-6: four cards;
* rungs 7-9: the bottom card too;
* rungs 10-12: five cards; second from the top too;
* from rung 13: six cards, all one colour; seven from rung 19; third
  from the top from rung 16.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

STEP = 0.02


class Grade(NamedTuple):
    rung: int
    cards: int
    asks: Tuple[int, ...]        # depths asked: 0 the top, -1 the bottom
    plain: bool                  # all one colour


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        cards=(3 if r < 4 else 4 if r < 10 else 5 if r < 13 else 6 if r < 19
               else 7),
        asks=((0,) if r < 7 else (0, -1) if r < 10 else (0, -1, 1) if r < 16
              else (0, -1, 1, 2)),
        plain=r >= 13)


class Card(NamedTuple):
    x: float
    y: float
    w: float
    h: float
    turn: float
    hue: float
    number: int                  # what is written on it, from 1


class Puzzle(NamedTuple):
    level: Grade
    cards: List[Card]            # from the bottom of the pile up
    tags: List[Tuple[float, float]]
    ask: int
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def inside(c: Card, x: float, y: float) -> bool:
    dx, dy = x - c.x, y - c.y
    cs, sn = math.cos(c.turn), math.sin(c.turn)
    return abs(dx * cs + dy * sn) <= c.w / 2 and \
        abs(-dx * sn + dy * cs) <= c.h / 2


def showing(cards: List[Card]) -> dict:
    """For each sample point of the page, the cards there, bottom up."""
    out = {}
    for i in range(int(S.W / STEP)):
        for j in range(int(1 / STEP)):
            x, y = (i + 0.5) * STEP, (j + 0.5) * STEP
            there = [k for k, c in enumerate(cards) if inside(c, x, y)]
            if there:
                out[(i, j)] = there
    return out


def order(cards: List[Card]) -> Optional[List[int]]:
    """The pile's order, top first, read only from who covers whom
    where it can be seen; None if that does not settle it."""
    over = set()
    for there in showing(cards).values():
        top = there[-1]
        for k in there[:-1]:
            over.add((top, k))
    n = len(cards)
    left = set(range(n))
    out = []
    while left:
        free = [k for k in left if not any((j, k) in over for j in left)]
        if len(free) != 1:
            return None
        out.append(free[0])
        left.discard(free[0])
    return out


def solve(p: Puzzle) -> Optional[int]:
    pile = order(p.cards)
    if pile is None:
        return None
    return p.cards[pile[p.ask]].number - 1


def corners(c: Card):
    return S.place([(-c.w / 2, -c.h / 2), (c.w / 2, -c.h / 2),
                    (c.w / 2, c.h / 2), (-c.w / 2, c.h / 2)], c.x, c.y, 1.0,
                   c.turn)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.cards
    ask = draw.choice(level.asks)
    want = S.slot(seed, n)
    said = {0: _('Which card is on top?'), -1: _('Which card is at the bottom?'),
            1: _('Which card is second from the top?'),
            2: _('Which card is third from the top?')}[ask]
    for _attempt in range(600):
        hue = draw.random()
        x, y = draw.uniform(0.5, S.W - 0.5), draw.uniform(0.38, 0.62)
        cards = []
        numbers = list(range(1, n + 1))
        draw.shuffle(numbers)
        for k in range(n):
            if k:
                a = draw.uniform(0, 2 * math.pi)
                d = draw.uniform(0.14, 0.24)
                x = min(S.W - 0.32, max(0.32, x + math.cos(a) * d))
                y = min(0.72, max(0.28, y + math.sin(a) * d))
            cards.append(Card(x, y, draw.uniform(0.3, 0.42),
                              draw.uniform(0.2, 0.3), draw.uniform(0, math.pi),
                              hue + (draw.uniform(-0.03, 0.03) if level.plain
                                     else k / float(n) + draw.uniform(-0.04, 0.04)),
                              numbers[k]))
        if not all(0.02 < px < S.W - 0.02 and 0.02 < py < 0.98
                   for c in cards for px, py in corners(c)):
            continue
        pile = order(cards)
        if pile is None:
            continue
        # The numbers are only names: the card asked for takes the dealt one.
        asked = pile[ask]
        other = [k for k in range(n) if cards[k].number == want + 1][0]
        a, b = cards[asked].number, cards[other].number
        cards[asked] = cards[asked]._replace(number=b)
        cards[other] = cards[other]._replace(number=a)
        # A place on each card, well inside what shows of it, for its number.
        seenat = showing(cards)
        tags = []
        for k in range(n):
            mine = {q for q, there in seenat.items() if there[-1] == k}
            deep = [q for q in mine
                    if all((q[0] + i, q[1] + j) in mine
                           for i in (-2, 0, 2) for j in (-2, 0, 2))]
            if not deep:
                break
            mx = sum(q[0] for q in deep) / float(len(deep))
            my = sum(q[1] for q in deep) / float(len(deep))
            q = min(deep, key=lambda q: (q[0] - mx) ** 2 + (q[1] - my) ** 2)
            tags.append(((q[0] + 0.5) * STEP, (q[1] + 0.5) * STEP))
        if len(tags) < n:
            continue
        return Puzzle(level, cards, tags, ask, draw.choice(S.PAPERS), said,
                      tuple(str(k + 1) for k in range(n)), want)
    raise RuntimeError('no pile for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    for c, (tx, ty) in zip(p.cards, p.tags):
        pts = corners(c)
        out.append(S.poly(pts, S.hsv(c.hue, 0.45, 0.88)))
        edge = S.hsv(c.hue, 0.6, 0.4)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            out.append(S.line(a[0], a[1], b[0], b[1], 0.005, edge))
    for c, (tx, ty) in zip(p.cards, p.tags):
        out.append(S.text(tx, ty, 0.05, str(c.number)))
    return out
