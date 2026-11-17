# -*- coding: utf-8 -*-
"""Same Instrument: is it the same instrument playing?

Two notes. Were they played on the same instrument, or on two? Low
down the notes are the same and the instruments quite unlike; then the
notes differ, so that it is the instrument that has to be heard and not
the note; then the instruments are of one family. From rung 10 there
are three notes, two on one instrument, and the question is which was
the odd one.

The ladder:

* rungs 1-3: the same note; instruments of different families;
* rungs 4-6: notes up to a third apart;
* rungs 7-9: instruments of one family, sometimes;
* rungs 10-12: three notes: which is on the other instrument?
* from rung 13: always of one family; notes up to an octave apart,
  and shorter every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import NamedTuple, Optional, Tuple

from . import scenes as S
from . import showing
from .i18n import _

SAME, DIFFERENT = 0, 1
FAMILIES = (('sine', 'flute', 'pad', 'glass'),
            ('organ', 'clarinet', 'brass', 'square'),
            ('pluck', 'bell', 'wood', 'metal'),
            ('growl', 'chirp', 'alien', 'zap'))


class Grade(NamedTuple):
    rung: int
    notes: int
    spread: float        # semitones the notes may differ by
    kin: float           # how often the two are of one family
    length: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        notes=2 if r < 10 else 3,
        spread=(0.0 if r < 4 else 4.0 if r < 13 else 12.0),
        kin=0.0 if r < 7 else 0.5 if r < 13 else 1.0,
        length=0.6 if r < 13 else max(0.15, 0.5 * 0.93 ** (r - 13)))


class Puzzle(NamedTuple):
    level: Grade
    names: Tuple[str, ...]       # the instruments
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
    voices = [n.voice for n in p.notes]
    if len(voices) == 2:
        return SAME if voices[0] == voices[1] else DIFFERENT
    return [k for k, v in enumerate(voices) if voices.count(v) == 1][0]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    family = draw.choice(FAMILIES)
    one = draw.choice(family)
    if draw.random() < level.kin:
        two = draw.choice([x for x in family if x != one])
    else:
        two = draw.choice(draw.choice([f for f in FAMILIES if f != family]))
    base = draw.uniform(260, 520)
    if level.notes == 2:
        answer = S.slot(seed, 2)
        voices = [0, 0] if answer == SAME else [0, 1]
        q = _('Listen. The same instrument, or different?')
        choices = (_('Same'), _('Different'))
    else:
        answer = S.slot(seed, 3)
        voices = [0, 0, 0]
        voices[answer] = 1
        q = _('Listen. Which note was on the other instrument?')
        choices = (_('First'), _('Second'), _('Third'))
    steps = [0.0] + [draw.uniform(-level.spread, level.spread)
                     for _k in voices[1:]]
    notes = tuple(showing.note(0.6 + k * (level.length + 0.4), level.length,
                               showing.semitones(base, steps[k]), 0.0, 0.7, v)
                  for k, v in enumerate(voices))
    end = notes[-1].t + notes[-1].dur
    return Puzzle(level, (one, two), draw.random(), (26, 28, 36), end + 0.05,
                  end + 6.0, notes,
                  (showing.patch(one, seed), showing.patch(two, seed + 1)),
                  q, choices, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = [S.text(S.W / 2, 0.5, 0.08, _('listen'), (200, 200, 210))]
    if judged:
        out.append(S.text(S.W / 2, 0.3, 0.045, ' / '.join(
            p.names if len({n.voice for n in p.notes}) > 1 else p.names[:1]),
            (160, 160, 175)))
    return out
