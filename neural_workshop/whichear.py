# -*- coding: utf-8 -*-
"""Which Ear: where is the sound?

A tone somewhere between the ears: to the left or to the right? Higher
up there are two tones, and the question is whether the second lay to
the left or the right of the first -- wherever the pair of them lay.

The ladder:

* rungs 1-3: far to one side;
* rungs 4-6: halfway;
* rungs 7-9: two tones; the second a quarter of the way across from
  the first;
* rungs 10-12: an eighth; the tones differ in pitch;
* from rung 13: closing toward one part in forty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import NamedTuple, Optional, Tuple

from . import scenes as S
from . import showing
from .i18n import _

LEFT, RIGHT = 0, 1


class Grade(NamedTuple):
    rung: int
    aside: float         # how far to the side, 1 all the way
    pair: bool
    pitch: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        aside=(0.9 if r < 4 else 0.5 if r < 7 else 0.25 if r < 10
               else 0.125 if r < 13 else max(0.025, 0.1 * 0.9 ** (r - 13))),
        pair=r >= 7,
        pitch=r >= 10)


class Puzzle(NamedTuple):
    level: Grade
    hue: float
    paper: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    if len(p.notes) == 1:
        return RIGHT if p.notes[0].pan > 0 else LEFT
    return RIGHT if p.notes[1].pan > p.notes[0].pan else LEFT


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, 2)
    sign = 1 if answer == RIGHT else -1
    freq = draw.uniform(330, 700)
    name = draw.choice(('sine', 'flute', 'organ', 'clarinet'))
    if level.pair:
        first = draw.uniform(-0.6, 0.6)
        second = first + sign * level.aside
        f2 = freq * (showing.semitones(1.0, draw.uniform(-4, 4))
                     if level.pitch else 1.0)
        notes = (showing.note(0.6, 0.5, freq, first, 0.7),
                 showing.note(1.5, 0.5, f2, second, 0.7))
        q = _('Listen. Was the second tone to the left of the first, or the '
              'right?')
    else:
        notes = (showing.note(0.6, 0.6, freq, sign * level.aside, 0.7),)
        q = _('Listen. Which side is the tone on?')
    end = notes[-1].t + notes[-1].dur
    return Puzzle(level, draw.random(), (26, 28, 36), end + 0.05, end + 6.0,
                  notes, (showing.patch(name, seed),), q,
                  (_('Left'), _('Right')), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    return [S.text(S.W / 2, 0.5, 0.08, _('listen'), (200, 200, 210))]
