# -*- coding: utf-8 -*-
"""Now and earlier: things show twice, and the answer is what is
different the second time.

Each trial shows a board of things, then *k - 1* empty frames at rung
k, then the board again with one difference; the question is put on
that second showing. Neither showing alone says anything about the
answer.

``moved``   four things, then the same four with one in another place:
            press the card of the thing that moved.
``new``     three things, then four in fresh places: press the card of
            the one that was not there before. The four cards are the
            four things showing.
``gone``    four things, then three of them in fresh places: press the
            card of the one that went. The cards are the one that went
            and three never shown, so the cards do not give it away.
``traded``  five things in a row, then the same row with two of them
            changed places and one of those two marked: press the place
            of the one it changed places with.

Chance from the second showing alone: one in four for each kind (for
``traded`` the marked place is never the answer and the other four are
equally likely). The cheap partial strategies, which the tests count:

``moved``   keeping where one thing was, chosen before the question:
            it pays if that one moved, a quarter of the time, and
            otherwise rules one card out: 1/4 + 3/4 * 1/3 = 1/2.
``new``     keeping one of the first three things rules one card out,
            for one in three; keeping two, one in two.
``gone``    keeping one of the first four things: right when it is the
            one that went, else no help: 1/4 + 3/4 * 1/4 = 7/16.
``traded``  keeping where one thing was: when it is one of the two
            that changed places (2 in 5) the answer follows from where
            it is now, else it rules its place out, leaving one in
            three: 2/5 + 3/5 * 1/3 = 3/5.

Each kind comes in two looks (see :mod:`framed`), so each rule has a
twin. Presses before the question is put are ignored; a wrong press
once it is put ends the trial.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed
from .i18n import _

KINDS = ('moved', 'new', 'gone', 'traded')
CARDS = 4
SPOTS = 9
ROW = 5                          # places in the traded row

QUESTIONS = {
    'moved': _('Which thing moved?'),
    'new': _('Which thing is new?'),
    'gone': _('Which thing is gone?'),
    'traded': _('Which one did the marked one change places with?'),
}


def frames(k: int):
    """First showing, k - 1 empty frames, second showing."""
    return (0,) + (-1,) * (k - 1) + (1,)


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    k = max(1, int(rung))
    data = {'look': look, 'hue': rng.randrange(len(framed.HUES_A)),
            'rim': rng.randrange(len(framed.RIMS)),
            'turn': rng.randrange(8),
            'place': (rng.random(), rng.random())}
    if kind == 'traded':
        things = rng.sample(range(framed.THINGS), ROW)
        a, b = rng.sample(range(ROW), 2)
        second = list(things)
        second[a], second[b] = second[b], second[a]
        marked, partner = (a, b) if rng.random() < 0.5 else (b, a)
        order = framed.port_order(look, ROW)
        data.update(first=tuple(things), second=tuple(second),
                    marked=marked)
        answer = order.index(partner)
        choices = tuple(str(p + 1) for p in range(ROW))
        return framed.puzzle(kind, k, frames(k), choices, answer, data,
                             QUESTIONS[kind])
    pool = list(range(framed.THINGS))
    rng.shuffle(pool)
    if kind == 'moved':
        things = pool[:4]
        first_spots = rng.sample(range(SPOTS), 4)
        mover = rng.randrange(4)
        second_spots = list(first_spots)
        second_spots[mover] = rng.choice(
            [s for s in range(SPOTS) if s not in first_spots])
        first = tuple(zip(things, first_spots))
        second = tuple(zip(things, second_spots))
        cards, key = list(things), things[mover]
    elif kind == 'new':
        old, fresh = pool[:3], pool[3]
        first = tuple(zip(old, rng.sample(range(SPOTS), 3)))
        now = old + [fresh]
        rng.shuffle(now)
        second = tuple(zip(now, rng.sample(range(SPOTS), 4)))
        cards, key = list(now), fresh
    elif kind == 'gone':
        shown, decoys = pool[:4], pool[4:7]
        went = rng.randrange(4)
        first = tuple(zip(shown, rng.sample(range(SPOTS), 4)))
        kept = [t for i, t in enumerate(shown) if i != went]
        rng.shuffle(kept)
        second = tuple(zip(kept, rng.sample(range(SPOTS), 3)))
        cards, key = [shown[went]] + decoys, shown[went]
    else:
        raise ValueError(kind)
    rng.shuffle(cards)
    order = framed.port_order(look, CARDS)
    # cards[place] is the thing on the card at that place; a port names
    # a place through the look's order.
    data.update(first=first, second=second, cards=tuple(cards))
    answer = order.index(cards.index(key))
    choices = tuple(str(p + 1) for p in range(CARDS))
    return framed.puzzle(kind, k, frames(k), choices, answer, data,
                         QUESTIONS[kind])


def card_of(puzzle: framed.Puzzle, port: int) -> int:
    """The thing on the card *port* presses."""
    order = framed.port_order(puzzle.data['look'], len(puzzle.choices))
    return puzzle.data['cards'][order[port]]


def place_of(puzzle: framed.Puzzle, port: int) -> int:
    """The place in the row *port* presses (``traded``)."""
    return framed.port_order(puzzle.data['look'], ROW)[port]
