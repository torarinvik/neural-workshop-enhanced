# -*- coding: utf-8 -*-
"""More or Less: which side has more, without counting?

Two clouds of dots flash up and are covered: which had more? Too quick
to count past the first rungs, so the sense of *how many* has to do it
-- and the dots are sized so that which cloud has more ink, or covers
more ground, says nothing about which has more dots.

From rung 7 some trials are the old conservation question instead: two
columns of dots, matched one to one, and then one column spreads out
(or bunches up) while everyone watches. Has either got more? Spreading
changes nothing -- "the same" is often the answer -- and when one has a
dot more, it is the one that was bunched up.

The ladder:

* rungs 1-3: two to one, a few dots, three seconds to look -- countable;
* rungs 4-6: three to two; a second and a half; the more numerous dots
  are the smaller, so the ink is no guide;
* rungs 7-9: four to three; a second; conservation columns too;
* rungs 10-12: five to four, the clouds mixed into one, two colours;
* from rung 13: the ratio closes toward 1.06, the flash shortens toward
  a quarter second, and up to forty dots a side.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

LEFT, RIGHT, SAME = 0, 1, 2
HUES = (((230, 80, 70), (60, 120, 230)), ((240, 170, 30), (120, 70, 200)),
        ((50, 160, 100), (220, 90, 160)), ((30, 160, 200), (240, 120, 40)))


class Grade(NamedTuple):
    rung: int
    ratio: float
    flash: float
    counts: Tuple[int, int]      # the smaller side
    ink: bool                    # the more numerous are smaller
    rows: bool                   # conservation trials
    mixed: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        ratio=(2.0 if r < 4 else 1.5 if r < 7 else 1.34 if r < 10
               else 1.25 if r < 13 else max(1.06, 1.22 - 0.008 * (r - 13))),
        flash=(3.0 if r < 4 else 1.5 if r < 7 else 1.0 if r < 10
               else 0.75 if r < 13 else max(0.25, 0.6 - 0.02 * (r - 13))),
        counts=((3, 6) if r < 4 else (6, 12) if r < 10 else (10, 20)
                if r < 13 else (14, min(40, 20 + (r - 13)))),
        ink=r >= 4,
        rows=r >= 7,
        mixed=r >= 10)


class Dot(NamedTuple):
    x: float
    y: float
    r: float
    side: int


class Puzzle(NamedTuple):
    level: Grade
    kind: str                    # 'flash' or 'rows'
    dots: List[Dot]              # flash: where they are
    rows: Tuple[int, int]        # rows: how many in each column
    spread: int                  # rows: which column moves (LEFT/RIGHT)
    factor: float                # rows: its spacing after, times before
    hues: Tuple[Tuple[int, int, int], Tuple[int, int, int]]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


#: Seconds the rows stand matched, and then move.
MATCHED, MOVING = 1.2, 1.0


def row_place(p: Puzzle, side: int, k: int, t: float) -> Tuple[float, float]:
    """Where dot *k* of column *side* is at time *t* (unit square)."""
    n = p.rows[side]
    gap = 0.8 / max(p.rows)
    if side == p.spread:
        a = min(1.0, max(0.0, (t - MATCHED) / MOVING))
        a = a * a * (3 - 2 * a)
        gap *= 1 + (p.factor - 1) * a
    mid = 0.5
    y = mid + (k - (n - 1) / 2) * gap
    return (0.3 if side == LEFT else 0.7), y


def _place(n: int, draw, box, r: float, taken: List[Dot], side: int,
           jitter: float) -> Optional[List[Dot]]:
    x0, y0, x1, y1 = box
    out = []
    for _k in range(n):
        for _try in range(300):
            rr = r * draw.uniform(1 - jitter, 1 + jitter)
            x, y = draw.uniform(x0 + rr, x1 - rr), draw.uniform(y0 + rr,
                                                               y1 - rr)
            if all(math.hypot(x - d.x, y - d.y) > rr + d.r + 0.008
                   for d in taken + out):
                out.append(Dot(x, y, rr, side))
                break
        else:
            return None
    return out


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    hues = draw.choice(HUES)
    if draw.random() < 0.5:
        hues = (hues[1], hues[0])
    choices = (_('Left'), _('Right')) + ((_('Same'),) if level.rows else ())
    if level.rows and draw.random() < 0.35:
        n = draw.randint(5, 9)
        same = draw.random() < 0.5
        spread = draw.choice((LEFT, RIGHT))
        rows = [n, n]
        if same:
            answer = SAME
            factor = draw.choice((1.5, 1.7, 0.6))
        else:
            # The spread column has a dot fewer; the other is bunched.
            rows[spread] = n - 1
            factor = 1.7
            answer = 1 - spread
        open_at = MATCHED + MOVING
        return Puzzle(level, 'rows', [], tuple(rows), spread, factor, hues,
                      open_at, open_at + 8.0, (), (),
                      _('Has either column more dots, or are they the same?'),
                      choices, answer)
    for _attempt in range(300):
        small = draw.randint(*level.counts)
        big = int(round(small * level.ratio))
        if big <= small:
            big = small + 1
        answer = draw.choice((LEFT, RIGHT))
        counts = [small, small]
        counts[answer] = big
        # Dot radii: equal, or the bigger count's dots smaller so that
        # the total ink is about the same or less.
        base = 0.34 / math.sqrt(max(counts) * 4.5)
        radii = [base, base]
        if level.ink:
            radii[answer] = base * math.sqrt(small / big) * \
                draw.uniform(0.85, 1.0)
        dots: List[Dot] = []
        ok = True
        for side in (LEFT, RIGHT):
            box = (0.03, 0.05, 0.97, 0.95) if level.mixed else \
                ((0.03, 0.05, 0.47, 0.95) if side == LEFT
                 else (0.53, 0.05, 0.97, 0.95))
            got = _place(counts[side], draw, box, radii[side], dots, side,
                         0.25 if level.ink else 0.05)
            if got is None:
                ok = False
                break
            dots += got
        if not ok:
            continue
        draw.shuffle(dots)
        q = (_('Which colour has more dots?') if level.mixed else
             _('Which side has more dots?'))
        ch = choices
        if level.mixed:
            ch = (_('Left colour'), _('Right colour')) + choices[2:]
        return Puzzle(level, 'flash', dots, tuple(counts), 0, 1.0, hues,
                      0.0, level.flash + 6.0, (), (), q, ch, answer)
    raise RuntimeError('no dots for rung %d' % rung)
