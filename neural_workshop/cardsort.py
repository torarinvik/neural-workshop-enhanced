# -*- coding: utf-8 -*-
"""Card Sort: sort by the rule, and notice when it silently changes.

Key cards stand in a row, each different from the others in every
property. Cards come one at a time and each goes under a key. Whether
it was right is all that is said: the rule -- match the colour, or the
shape, or the count -- is never shown, and after a run of right
answers it **changes without warning**. Finding the rule is half of it;
letting go of it when the answers turn wrong is the other half.

Every card is judged, so a run is many quick questions; with two keys
a guess is right half the time.

A run keeps one :class:`Sorter`, which holds the rule and the streak
across trials, whatever rung each trial is at.

The ladder:

* rungs 1-3: two keys, colour or shape, the rule changing after six
  right -- and said to have changed;
* rungs 4-6: three keys, count as well, said nothing;
* rungs 7-9: four keys, after five right;
* rungs 10-12: fill as well, after four right;
* rungs 13-15: after three to five, and the rule may go back to the
  one before;
* from rung 16: the rule changes after a random two to six cards,
  right or not.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _

DIMS = ('colour', 'shape', 'count', 'fill')


class Grade(NamedTuple):
    rung: int
    keys: int
    dims: int
    after: Tuple[int, int]    # right answers before the change, at most
    told: bool                # say when it changed
    back: bool                # may change back to the last rule
    blind: bool               # changes after cards, not right answers


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        keys=2 if r < 4 else 3 if r < 7 else 4,
        dims=2 if r < 4 else 3 if r < 10 else 4,
        after=((6, 6) if r < 7 else (5, 5) if r < 10 else (4, 4) if r < 13
               else (3, 5) if r < 16 else (2, 6)),
        told=r < 4,
        back=r >= 13,
        blind=r >= 16)


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    keys: List[G.Glyph]
    card: G.Glyph
    rule: str
    changed: bool             # the rule changed before this card
    question: str
    choices: Tuple[str, ...]
    answer: int


def _value(g: G.Glyph, dim: str) -> int:
    v = getattr(g, dim)
    return v - 1 if dim == 'count' else v


def key_for(keys: List[G.Glyph], card: G.Glyph, dim: str) -> int:
    for k, g in enumerate(keys):
        if _value(g, dim) == _value(card, dim):
            return k
    raise ValueError('no key matches')


class Sorter:
    """A run's rule, streak and look."""

    def __init__(self, seed: int) -> None:
        self.draw = random.Random(seed)
        self.look = G.look(self.draw, shapes=4, colours=4)
        self.rule: Optional[str] = None
        self.last: Optional[str] = None
        self.streak = 0
        self.since = 0
        self.need = 0
        self.changed = False

    def _switch(self, level: Grade) -> None:
        dims = list(DIMS[:level.dims])
        if self.rule in dims:
            dims.remove(self.rule)
        if level.back and self.last in dims and self.draw.random() < 0.4:
            new = self.last
        else:
            new = self.draw.choice(dims)
        self.last, self.rule = self.rule, new
        self.streak = 0
        self.since = 0
        self.need = self.draw.randint(*level.after)
        self.changed = True

    def next(self, rung: int) -> Puzzle:
        level = grade(rung)
        if self.rule is None or DIMS.index(self.rule) >= level.dims:
            self._switch(level)
            self.changed = False
        elif (level.blind and self.since >= self.need) or \
                (not level.blind and self.streak >= self.need):
            self._switch(level)
        keys = [G.Glyph(k, k, 1, k + 1, 0, k % G.FILLS, -1)
                for k in range(level.keys)]
        if level.keys == 4:
            keys[3] = keys[3]._replace(fill=self.draw.randrange(G.FILLS))
        for _k in range(200):
            card = G.Glyph(self.draw.randrange(level.keys),
                           self.draw.randrange(level.keys), 1,
                           self.draw.randrange(level.keys) + 1, 0,
                           self.draw.randrange(min(level.keys, G.FILLS)), -1)
            if level.dims < 4:
                card = card._replace(fill=0)
                keys = [g._replace(fill=0) for g in keys]
            dims = DIMS[:level.dims]
            spots = {key_for(keys, card, d) for d in dims
                     if any(_value(g, d) == _value(card, d) for g in keys)}
            if all(any(_value(g, d) == _value(card, d) for g in keys)
                   for d in dims) and len(spots) >= min(2, level.keys):
                break
        answer = key_for(keys, card, self.rule)
        changed, self.changed = self.changed, False
        return Puzzle(level, self.look, keys, card, self.rule, changed,
                      _('Which key does this card go under?'),
                      tuple(str(k + 1) for k in range(level.keys)), answer)

    def judged(self, right: bool) -> None:
        self.since += 1
        self.streak = self.streak + 1 if right else 0


class Reader:
    """The reference player: keeps the rules the answers allow."""

    def __init__(self) -> None:
        self.maybe: List[str] = list(DIMS)
        self.wrong: Optional[str] = None

    def pick(self, p: Puzzle) -> int:
        dims = [d for d in self.maybe if d in DIMS[:p.level.dims]]
        if not dims:
            dims = [d for d in DIMS[:p.level.dims] if d != self.wrong] \
                or list(DIMS[:p.level.dims])
            self.maybe = dims
        return key_for(p.keys, p.card, dims[0])

    def heard(self, p: Puzzle, chosen: int, right: bool) -> None:
        dims = [d for d in DIMS[:p.level.dims]]
        fits = [d for d in dims if key_for(p.keys, p.card, d) == chosen]
        if right:
            self.maybe = [d for d in self.maybe if d in fits] or fits
        else:
            self.wrong = fits[0] if fits else None
            self.maybe = [d for d in self.maybe if d not in fits]
