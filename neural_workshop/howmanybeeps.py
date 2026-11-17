# -*- coding: utf-8 -*-
"""How Many Beeps: count them.

A run of beeps. How many were there? Slow and even at first; then
quick, then uneven, then on different notes, and at last with other
sounds among them that are not to be counted: only the high beeps
count.

The ladder:

* rungs 1-3: one to three, slow;
* rungs 4-6: up to five, quicker;
* rungs 7-9: up to six, unevenly spaced;
* rungs 10-12: up to seven, on different notes, quicker;
* from rung 13: up to nine; low knocks among them, not to be
  counted; quicker every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import NamedTuple, Optional, Tuple

from . import scenes as S
from . import showing
from .i18n import _


class Grade(NamedTuple):
    rung: int
    most: int
    gap: float           # seconds from one beep to the next
    uneven: bool
    notes: bool
    knocks: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        most=3 if r < 4 else 5 if r < 7 else 6 if r < 10 else 7 if r < 13 else 9,
        gap=(0.5 if r < 4 else 0.3 if r < 7 else 0.24 if r < 10
             else 0.18 if r < 13 else max(0.09, 0.16 * 0.95 ** (r - 13))),
        uneven=r >= 7,
        notes=r >= 10,
        knocks=r >= 13)


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
    # The beeps are on the first instrument; the knocks on the second.
    return sum(1 for n in p.notes if n.voice == 0) - 1


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, level.most)
    count = answer + 1
    base = draw.uniform(700, 1000)
    dur = min(0.12, level.gap * 0.5)
    notes = []
    t = 0.6
    for _k in range(count):
        freq = showing.semitones(base, draw.uniform(-3, 3)) if level.notes \
            else base
        notes.append(showing.note(t, dur, freq, 0.0, 0.7, 0))
        t += level.gap * (draw.uniform(0.75, 1.8) if level.uneven else 1.0)
    end = notes[-1].t + dur
    patches = [showing.patch('sine', seed)]
    q = _('Listen. How many beeps?')
    if level.knocks:
        patches.append(showing.patch('wood', seed))
        for _k in range(draw.randint(1, 4)):
            notes.append(showing.note(draw.uniform(0.5, end), 0.08,
                                      draw.uniform(150, 220), 0.0, 0.7, 1))
        q = _('Listen. How many high beeps? (Do not count the knocks.)')
    notes.sort(key=lambda n: n.t)
    end = max(n.t + n.dur for n in notes)
    return Puzzle(level, draw.random(), (26, 28, 36), end + 0.05, end + 6.0,
                  tuple(notes), tuple(patches), q,
                  tuple(str(k + 1) for k in range(level.most)), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    return [S.text(S.W / 2, 0.5, 0.08, _('listen'), (200, 200, 210))]
