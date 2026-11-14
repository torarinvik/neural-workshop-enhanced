# -*- coding: utf-8 -*-
"""Triage: a budget of moves, more puzzles than it can pay for.

A round puts out a few cards. Each holds a small puzzle -- a row of
digits to be sorted into order by swapping neighbours -- and what solving
it pays. Every swap, on any card, comes out of one budget of moves for
the whole round. A card solved pays; a card worked on and left unsolved
pays nothing, and the moves spent on it are gone. So the skill is not
sorting, which is easy, but deciding what to spend thinking on: which
puzzles are worth their cost, in what order, and when to walk away from
one that turned out dearer than it looked.

The cost of a puzzle can be read off its card: the fewest swaps that
sort a row is the number of pairs of digits that stand in the wrong
order, so a row of nine can cost anything from one swap to thirty-six.
Reading that is part of the task. The ladder:

* more cards, longer rows, and a budget that covers a shrinking share of
  everything on the table -- from enough for all of it at rung one to
  under a third;
* from rung 8 what a card pays no longer follows what it costs, so a
  rich puzzle can be a cheap one and a poor one dear;
* from rung 12 the rows are dealt face down: a card shows how long its
  row is and what it pays, and turning it over costs a move. What it
  will cost is only known once that move is spent.

Par comes from a reference on the identical deal: it takes, again and
again, the card that pays most for each move it is expected to cost,
turns over face-down cards when they look worth it, and sorts by the
shortest route. Below rung twenty par gives some of that away; past it
par asks for more, up to the best any choice of cards could have done --
which needs a real plan, not a ratio.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

MOST_CARDS = 8
LONGEST = 9


class Grade(NamedTuple):
    rung: int
    cards: int
    shortest: int
    longest: int
    #: The budget as a share of the cost of everything on the table.
    tight: float
    #: Whether what a card pays is dealt apart from what it costs.
    traps: bool
    #: Whether rows are dealt face down, a move to turn over.
    hidden: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    longest = min(LONGEST, 3 + (r - 1) // 2)
    return Grade(
        rung=r,
        cards=min(MOST_CARDS, 2 + (r - 1) // 3),
        shortest=min(longest, 3 + (r - 1) // 6),
        longest=longest,
        tight=max(0.3, 1.3 - 0.05 * (r - 1)),
        traps=r >= 8,
        hidden=r >= 12,
    )


def inversions(row: Sequence[int]) -> int:
    """The fewest swaps of neighbours that sort *row*."""
    return sum(1 for i in range(len(row)) for j in range(i + 1, len(row))
               if row[i] > row[j])


class Card(NamedTuple):
    row: Tuple[int, ...]
    pays: int

    @property
    def cost(self) -> int:
        return inversions(self.row)


class Deal(NamedTuple):
    seed: int
    level: Grade
    cards: Tuple[Card, ...]
    budget: int

    def price(self, index: int) -> int:
        """Moves card *index* costs from the start, turning included."""
        return self.cards[index].cost + (1 if self.level.hidden else 0)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    cards = []
    for _index in range(level.cards):
        length = draw.randint(level.shortest, level.longest)
        row = list(range(1, length + 1))
        while inversions(row) == 0:
            draw.shuffle(row)
        cost = inversions(row)
        if level.traps:
            pays = draw.randint(1, 12)
        else:
            pays = max(1, cost + draw.randint(0, 2))
        cards.append(Card(tuple(row), pays))
    turning = 1 if level.hidden else 0
    total = sum(card.cost + turning for card in cards)
    cheapest = min(card.cost + turning for card in cards)
    budget = max(cheapest, int(round(level.tight * total)))
    return Deal(seed, level, tuple(cards), budget)


class Round:
    """One round of play on a deal."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        self.rows: List[List[int]] = [list(c.row) for c in dealt.cards]
        self.turned = set() if dealt.level.hidden else \
            set(range(len(dealt.cards)))
        self.solved: set = set()
        self.open: Optional[int] = None
        self.used = 0
        self.value = 0
        self.ended = False

    @property
    def moves_left(self) -> int:
        return self.deal.budget - self.used

    @property
    def over(self) -> bool:
        return (self.ended or self.moves_left <= 0
                or len(self.solved) == len(self.rows))

    def open_card(self, index: int) -> bool:
        if self.over or not 0 <= index < len(self.rows) \
                or index in self.solved:
            return False
        if index not in self.turned:
            self.turned.add(index)
            self.used += 1
        self.open = index
        return True

    def swap(self, at: int) -> bool:
        if self.over or self.open is None:
            return False
        row = self.rows[self.open]
        if not 0 <= at < len(row) - 1:
            return False
        row[at], row[at + 1] = row[at + 1], row[at]
        self.used += 1
        if inversions(row) == 0:
            self.solved.add(self.open)
            self.value += self.deal.cards[self.open].pays
            self.open = None
        return True

    def done(self) -> None:
        self.ended = True


def best(dealt: Deal) -> int:
    """The most any choice of cards could earn: a knapsack."""
    table = [0] * (dealt.budget + 1)
    for index, card in enumerate(dealt.cards):
        price = dealt.price(index)
        for room in range(dealt.budget, price - 1, -1):
            table[room] = max(table[room], table[room - price] + card.pays)
    return table[dealt.budget]


def expected_cost(length: int) -> float:
    return length * (length - 1) / 4.0


def reference_move(play: Round) -> Tuple[str, int]:
    """The reference's next action: ('open', i), ('swap', j) or
    ('done', 0). It sees only what the screen shows."""
    if play.open is not None:
        row = play.rows[play.open]
        if inversions(row) <= play.moves_left:
            return ('swap', next(j for j in range(len(row) - 1)
                                 if row[j] > row[j + 1]))
    choice, rate = None, 0.0
    for index, card in enumerate(play.deal.cards):
        if index in play.solved:
            continue
        if index in play.turned:
            cost = inversions(play.rows[index])
            if cost > play.moves_left:
                continue
        else:
            cost = expected_cost(len(card.row)) + 1
            if play.moves_left < 2:
                continue
        if card.pays / max(cost, 0.5) > rate:
            choice, rate = index, card.pays / max(cost, 0.5)
    if choice is None:
        return ('done', 0)
    if choice in play.turned:
        row = play.rows[choice]
        if play.open != choice:
            return ('open', choice)
        return ('swap', next(j for j in range(len(row) - 1)
                             if row[j] > row[j + 1]))
    return ('open', choice)


def act(play: Round, move: Tuple[str, int]) -> None:
    kind, at = move
    if kind == 'open':
        play.open_card(at)
    elif kind == 'swap':
        play.swap(at)
    else:
        play.done()


def reference_round(dealt: Deal) -> Round:
    play = Round(dealt)
    for _step in range(10000):
        if play.over:
            break
        act(play, reference_move(play))
    return play


def par(dealt: Deal) -> float:
    from .ui.rungtask import ladder_par
    return ladder_par(dealt.level.rung, reference_round(dealt).value, 0.0,
                      best(dealt))
