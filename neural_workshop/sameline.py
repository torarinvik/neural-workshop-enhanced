# -*- coding: utf-8 -*-
"""Same Line?: follow one line through a tangle.

Lines run from the left of the page to the right, crossing over one
another on the way, all in the same ink. Low down, two dots are marked,
one at a left end and one at a right: are they on the same line? Higher
up one left end is marked and the question is which right end it comes
out at.

The ladder:

* rungs 1-3: three lines, crossing in two places; same line or not;
* rungs 4-6: four lines, three stretches;
* rungs 7-9: which end does it reach?
* rungs 10-12: five lines, four stretches;
* from rung 13: six lines, and a longer tangle every three rungs.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

YES, NO = 0, 1
X0, X1 = 0.14, S.W - 0.14


class Grade(NamedTuple):
    rung: int
    lines: int
    stretches: int
    which: bool          # asks which end, not same-or-not


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        lines=3 if r < 4 else 4 if r < 10 else 5 if r < 13 else 6,
        stretches=(2 if r < 4 else 3 if r < 10 else 4 if r < 13
                   else min(9, 5 + (r - 13) // 3)),
        which=r >= 7)


class Puzzle(NamedTuple):
    level: Grade
    slots: List[List[int]]       # slots[b][i]: line i's slot at boundary b
    ease: List[List[float]]      # how each line leans within each stretch
    start: int                   # the line marked on the left
    end: int                     # the slot marked on the right (same-or-not)
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def height(level: Grade, slot: float) -> float:
    return 0.9 - 0.8 * slot / (level.lines - 1)


def solve(p: Puzzle) -> int:
    out = p.slots[-1][p.start]
    if p.level.which:
        return out
    return YES if out == p.end else NO


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.lines
    for _attempt in range(500):
        slots = [list(range(n))]
        for _b in range(level.stretches):
            nxt = list(slots[-1])
            # Every stretch moves most of the lines.
            for _s in range(n - 1):
                i, j = draw.sample(range(n), 2)
                nxt[i], nxt[j] = nxt[j], nxt[i]
            slots.append(nxt)
        if any(a == b for a, b in zip(slots, slots[1:])):
            continue
        ease = [[draw.uniform(0.7, 1.45) for _i in range(n)]
                for _b in range(level.stretches)]
        start = draw.randrange(n)
        out = slots[-1][start]
        if level.which:
            answer = S.slot(seed, n)
            if out != answer:
                continue
            end = out
            q = _('Which end does the marked line reach?')
            choices = tuple(str(k + 1) for k in range(n))
        else:
            answer = S.slot(seed, 2)
            end = out if answer == YES else \
                draw.choice([s for s in range(n) if s != out])
            q = _('Are the two dots on the same line?')
            choices = (_('Yes'), _('No'))
        return Puzzle(level, slots, ease, start, end, draw.random(),
                      draw.choice(S.PAPERS), q, choices, answer)
    raise RuntimeError('no tangle for rung %d' % rung)


def course(p: Puzzle, i: int, steps: int = 12) -> List[Tuple[float, float]]:
    """Line i's way across the page."""
    b = p.level.stretches
    pts = []
    for s in range(b):
        y0 = height(p.level, p.slots[s][i])
        y1 = height(p.level, p.slots[s + 1][i])
        for k in range(steps + (1 if s == b - 1 else 0)):
            u = k / float(steps)
            v = (1 - math.cos(math.pi * u ** p.ease[s][i])) / 2
            pts.append((X0 + (X1 - X0) * (s + u) / b, y0 + (y1 - y0) * v))
    return pts


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    ink = S.hsv(p.hue, 0.5, 0.35)
    red = (215, 60, 60)
    out = []
    n = p.level.lines
    for i in range(n):
        pts = course(p, i)
        colour = red if judged and i == p.start else ink
        for a, b in zip(pts, pts[1:]):
            out.append(S.line(a[0], a[1], b[0], b[1], 0.007, colour))
    out.append(S.disc(X0 - 0.03, height(p.level, p.start), 0.022, red))
    if p.level.which:
        for k in range(n):
            y = height(p.level, k)
            out.append(S.text(X1 + 0.06, y, 0.045, str(k + 1)))
            out.append(S.hit(X1 + 0.01, y - 0.04, 0.12, 0.08, k))
    else:
        out.append(S.disc(X1 + 0.03, height(p.level, p.end), 0.022, red))
    return out
