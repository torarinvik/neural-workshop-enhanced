# -*- coding: utf-8 -*-
"""Carried through: a state is shown once, then changed by events
shown one a frame; the question is where the state stands now.

Rung k has k events, and the question is put on the frame showing the
last of them.

``count``   a counter shows its value, then each frame shows a step,
            one or two up or down: press the card with the total. The
            four cards are four numbers in a row, and where in the row
            the total falls is drawn at random, so the cards say
            nothing of it.
``arrows``  a marker shows on one of four squares, two by two, then
            each frame shows an arrow, straight or slanting, and the
            marker moves one square that way, coming back in on the
            other side when it would leave the board: press the square
            the marker is on now. A straight arrow moves it to a square
            beside, a slanting one to the square across; each of the
            three is drawn as often.

Chance from the frame showing when the question is put (the last step,
or the last arrow, and the cards): one in four. The deal is made from
the end backwards -- the total and its place among the cards first,
then the steps, then the start -- so neither the last step nor the
numbers on the cards lean towards any card.

The cheap partial strategy is to keep the start and drop the events.
For the count, of the four totals one or two from the start, the best
guess among those on the cards is right half the time at rung 1, and
it falls off as the rungs add steps, to about a third by rung 3. For
the marker it earns a third at rungs 1 and 2 (the marker has left the
start at rung 1, and is back on it a third of the time at rung 2) and
little over a quarter from rung 3 on. The tests count both.

The count comes in two looks (see :mod:`framed`): numbers in look 0,
and piles of beads in look 1, with the ports the other way round. The
marker is drawn with chevrons, in look 1.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional, Tuple

from . import framed
from .i18n import _

KINDS = ('count', 'arrows')
CARDS = 4
#: Straight, then slanting: each moves the marker up or down a row,
#: left or right a column, or both.
ARROWS = ('up', 'down', 'left', 'right',
          'up-left', 'up-right', 'down-left', 'down-right')
#: The arrows that move it a row, a column, and both.
EFFECTS = ((0, 1), (2, 3), (4, 5, 6, 7))
#: How wide the range the cards start in is.
SPREAD = 7
#: What one event does to the count. Steps of two as well as one keep
#: the total's evenness from following the start's.
STEPS = (-2, -1, 1, 2)

QUESTIONS = {
    'count': _('What is the count now?'),
    'arrows': _('Where is the marker now?'),
}


def moved(cell: int, arrow: int) -> int:
    """Square *cell* (0 1 / 2 3, rows from the top) after one *arrow*,
    wrapping round the edges."""
    row, col = divmod(cell, 2)
    name = ARROWS[arrow]
    if 'up' in name or 'down' in name:
        row = 1 - row
    if 'left' in name or 'right' in name:
        col = 1 - col
    return row * 2 + col


def walked(cell: int, arrows: Tuple[int, ...]) -> int:
    for arrow in arrows:
        cell = moved(cell, arrow)
    return cell


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    k = max(1, int(rung))
    data = {'look': look, 'hue': rng.randrange(len(framed.HUES_A)),
            'rim': rng.randrange(len(framed.RIMS)),
            'place': (rng.random(), rng.random())}
    order = framed.port_order(look, CARDS)
    if kind == 'count':
        # Far enough up that no step takes the count below nothing.
        low = 2 * k + rng.randrange(SPREAD)      # the first card's number
        slot = rng.randrange(CARDS)
        total = low + slot
        steps = tuple(rng.choice(STEPS) for _s in range(k))
        data.update(start=total - sum(steps), steps=steps,
                    cards=tuple(low + i for i in range(CARDS)))
        answer = order.index(slot)
    elif kind == 'arrows':
        start = rng.randrange(CARDS)
        arrows = tuple(rng.choice(rng.choice(EFFECTS)) for _a in range(k))
        data.update(start=start, arrows=arrows)
        answer = order.index(walked(start, arrows))
    else:
        raise ValueError(kind)
    frames = tuple(range(k + 1))
    choices = tuple(str(p + 1) for p in range(CARDS))
    return framed.puzzle(kind, k, frames, choices, answer, data,
                         QUESTIONS[kind])


def place_of(puzzle: framed.Puzzle, port: int) -> int:
    """The card (count) or square (arrows) *port* presses."""
    return framed.port_order(puzzle.data['look'], CARDS)[port]
