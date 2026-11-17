# -*- coding: utf-8 -*-
"""Up or Down: did the tune go up or down?

Two tones: is the second higher than the first, or lower? A brighter
tone sounds higher than a duller one on the same note, so higher up the
lower tone is the brighter. From rung 10 there are three tones and the
question is which was the highest.

The ladder:

* rungs 1-3: a fifth apart;
* rungs 4-6: a third; the lower tone brighter;
* rungs 7-9: a semitone;
* rungs 10-12: three tones, a semitone apart: which was highest?
* from rung 13: closing toward a twentieth of a semitone.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from . import showing
from .i18n import _

UP, DOWN = 0, 1


class Grade(NamedTuple):
    rung: int
    tones: int
    apart: float         # semitones
    bright: bool         # the lower tone the brighter


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        tones=2 if r < 10 else 3,
        apart=(7.0 if r < 4 else 4.0 if r < 7 else 1.0 if r < 13
               else max(0.05, 0.7 * 0.85 ** (r - 13))),
        bright=r >= 4)


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
    pitches = [n.freq for n in p.notes]
    if len(pitches) == 2:
        return UP if pitches[1] > pitches[0] else DOWN
    return pitches.index(max(pitches))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.tones
    base = draw.uniform(260, 620)
    if n == 2:
        answer = S.slot(seed, 2)
        steps: List[float] = [0.0, level.apart if answer == UP else -level.apart]
        q = _('Listen. Did it go up or down?')
        choices = (_('Up'), _('Down'))
    else:
        answer = S.slot(seed, 3)
        lower = [-level.apart, -level.apart * draw.uniform(1.5, 2.5)]
        draw.shuffle(lower)
        steps = lower[:]
        steps.insert(answer, 0.0)
        q = _('Listen. Which tone was the highest?')
        choices = (_('First'), _('Second'), _('Third'))
    top = max(steps)
    notes = tuple(showing.note(
        0.6 + 0.75 * k, 0.5, showing.semitones(base, s), 0.0, 0.7, 0,
        (0.35 if s == top else 0.95) if level.bright else 0.7)
        for k, s in enumerate(steps))
    end = notes[-1].t + notes[-1].dur
    name = draw.choice(('organ', 'clarinet', 'brass', 'flute'))
    return Puzzle(level, draw.random(), (26, 28, 36), end + 0.05, end + 6.0,
                  notes, (showing.patch(name, seed),), q, choices, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    return [S.text(S.W / 2, 0.5, 0.08, _('listen'), (200, 200, 210))]
