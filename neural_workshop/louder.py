# -*- coding: utf-8 -*-
"""Louder: which tone was the loudest?

Tones one after another. Which was the loudest? A higher tone sounds
louder than a lower one of the same strength and a longer one louder
than a shorter, so higher up the loudest tone is the lower and the
shorter; and the whole trial is played now quietly, now loudly, so that
no one level can be learnt by heart.

The ladder:

* rungs 1-3: two tones, one twice as strong;
* rungs 4-6: half as strong again; the quieter one higher;
* rungs 7-9: a quarter; the quieter one longer;
* rungs 10-12: three tones; an eighth;
* from rung 13: closing toward one part in thirty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from . import showing
from .i18n import _


class Grade(NamedTuple):
    rung: int
    tones: int
    ratio: float
    pitch: bool          # the quieter higher
    length: bool         # the quieter longer


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        tones=2 if r < 10 else 3,
        ratio=(2.0 if r < 4 else 1.5 if r < 7 else 1.25 if r < 10
               else 1.125 if r < 13 else max(1.035, 1.1 - 0.004 * (r - 13))),
        pitch=r >= 4,
        length=r >= 7)


class Puzzle(NamedTuple):
    level: Grade
    gains: List[float]
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
    # The strength of each tone as it was played.
    played = [n.gain for n in p.notes]
    return played.index(max(played))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.tones
    answer = S.slot(seed, n)
    quiet = draw.uniform(0.25, 0.9 / level.ratio)
    gains = [quiet * draw.uniform(0.985, 1.0) for _k in range(n)]
    gains[answer] = quiet * level.ratio
    base = draw.uniform(330, 660)
    notes = []
    t = 0.6
    for k in range(n):
        loud = k == answer
        freq = base * (1.0 if loud or not level.pitch
                       else showing.semitones(1.0, draw.uniform(3, 7)))
        dur = 0.45 if loud or not level.length else draw.uniform(0.65, 0.8)
        notes.append(showing.note(t, dur, freq, 0.0, gains[k]))
        t += dur + 0.5
    end = t - 0.5
    names = (_('First'), _('Second'), _('Third'))[:n]
    return Puzzle(level, gains, draw.random(), (26, 28, 36), end + 0.05,
                  end + 6.0, tuple(notes), (showing.patch('sine', seed),),
                  _('Listen. Which tone was the loudest?'), names, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    return [S.text(S.W / 2, 0.5, 0.08, _('listen'), (200, 200, 210))]
