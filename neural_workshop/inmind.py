# -*- coding: utf-8 -*-
"""Held in mind: the answer is how the frame showing stands to one that
is no longer showing.

Looking back asks what an earlier frame held. Here the earlier frame
is only half of it, and the frame showing the other half: neither
alone says anything about the answer.

``changed``  four tiles show, each a hue, and then show again with one
             of them another hue: press the port of the tile that
             changed. At rung k the tiles are empty for k - 1 frames
             between the two showings.
``swapped``  one of four boxes lights and goes out; then, a frame at a
             time, two boxes are joined and what they hold changes
             places: press the port of the box the light is in now.
             Rung k has k such frames.

Presses before the question is put are ignored; a wrong press once it
is put ends the trial. From the frame showing when the question is put
every tile is as likely as another to be the one that changed, and
every box as likely to hold the light.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional, Sequence, Tuple

from .i18n import _
from .lookback import ANSWER, FRAME, HUES, Puzzle

KINDS = ('changed', 'swapped')
PLACES = 4
LAYOUTS = ('row', 'column', 'square')


def carried(cell: int, pairs: Sequence[Tuple[int, int]]) -> int:
    """Where what began in *cell* is after each of *pairs* changed
    places in turn."""
    for a, b in pairs:
        cell = b if cell == a else a if cell == b else cell
    return cell


def deal(kind: str, rung: int,
         rng: Optional[random.Random] = None) -> Puzzle:
    rng = rng or random.Random()
    k = max(1, int(rung))
    data = {'hue': rng.randrange(len(HUES)), 'layout': rng.choice(LAYOUTS)}
    choices = tuple(str(place + 1) for place in range(PLACES))
    if kind == 'changed':
        first = [rng.randrange(len(HUES)) for _p in range(PLACES)]
        answer = rng.randrange(PLACES)
        second = list(first)
        second[answer] = rng.choice([hue for hue in range(len(HUES))
                                     if hue != first[answer]])
        data['tiles'] = (tuple(first), tuple(second))
        # Frame 0 is the first showing and frame k the second; the
        # frames between are empty.
        frames = (0,) + (-1,) * (k - 1) + (1,)
        question = _('Which tile changed?')
    else:
        cell = rng.randrange(PLACES)
        pairs = tuple(tuple(sorted(rng.sample(range(PLACES), 2)))
                      for _f in range(k))
        data['pairs'] = pairs
        answer = carried(cell, pairs)
        frames = (cell,) + (-1,) * k
        question = _('Which box is the light in now?')
    # Asked on the last frame: the second showing, or the last swap.
    open_at = k * FRAME
    return Puzzle(kind, k, frames, choices, answer, open_at,
                  open_at + ANSWER, (), (), data, question)
