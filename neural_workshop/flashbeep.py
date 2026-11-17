# -*- coding: utf-8 -*-
"""Flash and Beep: the eye and the ear, together.

A lamp flashes and a beep sounds. Low down the question is which came
first. Higher up the lamp flashes a few times while beeps sound, and
the question is how many times it flashed -- the beeps are a different
number, and the ear is quick to tell the eye what it saw.

The ladder:

* rungs 1-3: which came first, two fifths of a second apart;
* rungs 4-6: a seventh of a second;
* rungs 7-9: a fourteenth; how many flashes too, one or two;
* rungs 10-12: a twenty-fifth; up to three flashes;
* from rung 13: up to four flashes, quicker; the gap closing toward
  a hundredth of a second.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from . import showing
from .i18n import _

FLASH, BEEP = 0, 1
LIT = 0.05           # seconds a flash lasts


class Grade(NamedTuple):
    rung: int
    gap: float           # seconds between flash and beep
    flashes: int         # most, when they are counted; 0 never counted
    pace: float          # seconds from flash to flash


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        gap=(0.4 if r < 4 else 0.14 if r < 7 else 0.07 if r < 10
             else 0.04 if r < 13 else max(0.01, 0.035 * 0.9 ** (r - 13))),
        flashes=0 if r < 7 else 2 if r < 10 else 3 if r < 13 else 4,
        pace=0.14 if r < 13 else 0.1)


class Puzzle(NamedTuple):
    level: Grade
    kind: str                    # 'first' or 'count'
    flashes: List[float]         # when each begins
    hue: float
    paper: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def lit(p: Puzzle, t: float) -> bool:
    return any(f <= t < f + LIT for f in p.flashes)


def solve(p: Puzzle) -> int:
    if p.kind == 'first':
        return FLASH if p.flashes[0] < p.notes[0].t else BEEP
    return len(p.flashes) - 1


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    kind = 'count' if level.flashes and draw.random() < 0.5 else 'first'
    t0 = draw.uniform(0.8, 1.4)
    freq = draw.uniform(600, 1000)
    if kind == 'first':
        answer = S.slot(seed, 2)
        flashes = [t0 if answer == FLASH else t0 + level.gap]
        notes = (showing.note(t0 + level.gap if answer == FLASH else t0, 0.03,
                              freq, 0.0, 0.7),)
        q = _('Which came first, the flash or the beep?')
        choices = (_('Flash'), _('Beep'))
    else:
        answer = S.slot(seed, level.flashes)
        count = answer + 1
        flashes = [t0 + k * level.pace for k in range(count)]
        # A different number of beeps, to lead the eye astray.
        beeps = draw.choice([b for b in range(1, level.flashes + 2)
                             if b != count])
        notes = tuple(showing.note(t0 + k * level.pace * 0.9, 0.02, freq, 0.0,
                                   0.7) for k in range(beeps))
        q = _('How many times did the lamp flash?')
        choices = tuple(str(k + 1) for k in range(level.flashes))
    end = max(flashes[-1] + LIT, notes[-1].t + notes[-1].dur)
    return Puzzle(level, kind, flashes, draw.random(), (26, 28, 36),
                  end + 0.05, end + 6.0, notes, (showing.patch('sine', seed),),
                  q, choices, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    on = lit(p, t) and not judged
    return [S.ring(S.W / 2, 0.5, 0.2, 0.006, (90, 94, 110)),
            S.disc(S.W / 2, 0.5, 0.19,
                   S.hsv(p.hue, 0.25, 1.0) if on else (44, 47, 58))]
