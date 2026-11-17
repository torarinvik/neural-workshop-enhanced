# -*- coding: utf-8 -*-
"""Number Line: what number is the mark at?

A line with a number at each end and a mark somewhere along it. What
number is at the mark? Higher up the question also runs the other way:
several marks, and which of them is at a given number. A question of
proportion, seen and not counted.

The ladder:

* rungs 1-3: nought to a hundred; three answers, thirty apart;
* rungs 4-6: four answers, fifteen apart;
* rungs 7-9: any ends; ten parts in a hundred apart; which mark too;
* rungs 10-12: seven parts in a hundred;
* from rung 13: five answers, six from rung 16, closing toward one
  and a half parts in a hundred.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

X0, X1 = 0.16, S.W - 0.16


class Grade(NamedTuple):
    rung: int
    answers: int
    apart: float         # as a share of the line
    ends: bool           # any ends, not nought and a hundred
    marks: bool          # which-mark questions too


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        answers=3 if r < 4 else 4 if r < 13 else 5 if r < 16 else 6,
        apart=(0.3 if r < 4 else 0.15 if r < 7 else 0.1 if r < 10
               else 0.07 if r < 13 else max(0.015, 0.05 * 0.92 ** (r - 13))),
        ends=r >= 7,
        marks=r >= 7)


class Puzzle(NamedTuple):
    level: Grade
    kind: str                    # 'number' or 'mark'
    low: int
    high: int
    values: List[int]            # the answers' numbers, rising
    asked: int                   # the number at the mark, or asked for
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def along(p: Puzzle, value: float) -> float:
    return X0 + (X1 - X0) * (value - p.low) / float(p.high - p.low)


def solve(p: Puzzle) -> int:
    # The mark's place, read back as a number.
    x = along(p, p.asked)
    read = p.low + (x - X0) / (X1 - X0) * (p.high - p.low)
    gaps = [abs(v - read) for v in p.values]
    return gaps.index(min(gaps))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.answers
    low, span = 0, 100
    if level.ends:
        low = draw.choice((0, 0, 10, 20, 50, 100, 250))
        span = draw.choice((50, 80, 100, 200, 400, 1000))
    step = max(1, int(round(level.apart * span)))
    room = span - step * (n - 1)
    first = low + draw.randint(max(1, int(room * 0.08)),
                               max(1, int(room * 0.92)))
    values = [first + k * step for k in range(n)]
    answer = S.slot(seed, n)
    kind = 'mark' if level.marks and draw.random() < 0.4 else 'number'
    if kind == 'number':
        q = _('What number is at the mark?')
        choices = tuple(str(v) for v in values)
    else:
        q = _('Which mark is at %d?') % values[answer]
        choices = tuple(str(k + 1) for k in range(n))
    return Puzzle(level, kind, low, low + span, values, values[answer],
                  draw.random(), draw.choice(S.PAPERS), q, choices, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    ink = S.hsv(p.hue, 0.5, 0.35)
    red = (215, 60, 60)
    y = 0.45
    out = [S.line(X0, y, X1, y, 0.008, ink),
           S.line(X0, y - 0.05, X0, y + 0.05, 0.008, ink),
           S.line(X1, y - 0.05, X1, y + 0.05, 0.008, ink),
           S.text(X0, y - 0.11, 0.05, str(p.low)),
           S.text(X1, y - 0.11, 0.05, str(p.high))]
    if p.kind == 'number':
        x = along(p, p.asked)
        out.append(S.line(x, y - 0.045, x, y + 0.045, 0.006, red))
        if judged:
            out.append(S.text(x, y + 0.1, 0.045, str(p.asked)))
        return out
    n = len(p.values)
    mid = sum(along(p, v) for v in p.values) / n
    step = max(0.085, along(p, p.values[1]) - along(p, p.values[0]))
    for k, v in enumerate(p.values):
        x = along(p, v)
        out.append(S.line(x, y - 0.04, x, y + 0.04, 0.004, red))
        lx = min(S.W - 0.05, max(0.05, mid + (k - (n - 1) / 2.0) * step))
        out.append(S.line(x, y + 0.045, lx, y + 0.2, 0.002, (150, 150, 160)))
        out.append(S.text(lx, y + 0.25, 0.045, str(k + 1)))
        out.append(S.hit(lx - 0.04, y + 0.2, 0.08, 0.1, k))
    return out
