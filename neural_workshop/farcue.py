# -*- coding: utf-8 -*-
"""A cue far back: one of four things is marked as the one that
matters, then many frames of look-alike things go by unmarked, then
the question.

For a learner whose memory is too short to keep every frame: the
frames in between are made of the same things in the same places, so
nothing tells it which frame to keep except the mark.

``marked``  four things show in four panels, one of them marked; then
            a run of frames each showing four of the same kind of thing
            in the panels, none marked; then the four things of the
            first frame on four cards, in a new order: press the card
            of the one that was marked.

Rung k puts 2**k look-alike frames between the mark and the question:
2, 4, 8, 16, 32. The ladder tops out at rung 5: higher rungs play as
rung 5.

Chance from the frame the question is put on: one in four, since the
cards are the four things of the first frame in an order drawn at
random. The cheap partial strategies earn no more: keeping the first
frame without the mark leaves the four cards alike, and keeping where
the mark was without what was there says nothing, since the cards are
not in the panels' order. Both are one in four; the tests count them.

Two looks (see :mod:`framed`): shapes in a row of panels, marked with
a ring, cards below, in look 0; beads in a square of panels, marked
with a pointer, cards to the right and the other way round, in look 1.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed
from .i18n import _

KINDS = ('marked',)
PANELS = 4
CARDS = 4
TOP = 5


def gap(rung: int) -> int:
    """Look-alike frames between the mark and the question."""
    return 2 ** min(TOP, max(1, int(rung)))


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    if kind != 'marked':
        raise ValueError(kind)
    k = max(1, int(rung))
    n = gap(k)
    first = rng.sample(range(framed.THINGS), PANELS)
    marked = rng.randrange(PANELS)
    fillers = tuple(tuple(rng.sample(range(framed.THINGS), PANELS))
                    for _f in range(n))
    cards = list(first)
    rng.shuffle(cards)
    order = framed.port_order(look, CARDS)
    data = {'look': look, 'hue': rng.randrange(len(framed.HUES_A)),
            'rim': rng.randrange(len(framed.RIMS)),
            'place': (rng.random(), rng.random()),
            'first': tuple(first), 'marked': marked, 'fillers': fillers,
            'cards': tuple(cards)}
    answer = order.index(cards.index(first[marked]))
    frames = (0,) + (1,) * n + (2,)
    choices = tuple(str(p + 1) for p in range(CARDS))
    return framed.puzzle(kind, k, frames, choices, answer, data,
                         _('Which one was marked?'))


def card_of(puzzle: framed.Puzzle, port: int) -> int:
    order = framed.port_order(puzzle.data['look'], CARDS)
    return puzzle.data['cards'][order[port]]
