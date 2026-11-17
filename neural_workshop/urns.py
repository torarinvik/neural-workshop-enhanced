# -*- coding: utf-8 -*-
"""Which Urn?: some balls were drawn; from which kind of urn?

Two kinds of urn, their balls shown, and how many urns of each kind
there are. One urn was picked at random and some balls drawn from it;
they are shown. From which kind did they more likely come?

The answer is the kind more likely **given what was drawn** -- the
posterior, by Bayes -- not whichever urn was really picked, so a
right answer is right however the draw happened to fall. A deal is kept
only when one kind is clearly more likely: by at least the rung's
margin in log-odds.

The ladder:

* rungs 1-3: one urn of each kind, nine to one against one to nine;
  one to three balls drawn;
* rungs 4-6: seven to three against three to seven; up to five drawn,
  some of each colour;
* rungs 7-9: three colours;
* rungs 10-12: more urns of one kind than the other -- the draw and the
  odds may pull different ways;
* rungs 13-15: small urns, drawn **without** putting back;
* from rung 16: the margin narrows, and more balls are drawn.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

LEFT, RIGHT = 0, 1
COLOURS = ((220, 60, 60), (50, 110, 220), (240, 190, 40), (60, 170, 90))


class Grade(NamedTuple):
    rung: int
    colours: int
    size: Tuple[int, int]     # balls in an urn
    draws: Tuple[int, int]
    priors: bool
    replace: bool
    margin: float             # least |log odds|


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        colours=2 if r < 7 else 3,
        size=(10, 10) if r < 13 else (6, 9),
        draws=((1, 3) if r < 4 else (3, 5) if r < 16
               else (4, min(12, 5 + (r - 16) // 2))),
        priors=r >= 10,
        replace=r < 13,
        margin=(2.0 if r < 4 else 1.2 if r < 10 else 0.9 if r < 16
                else max(0.25, 0.8 - 0.04 * (r - 16))))


class Puzzle(NamedTuple):
    level: Grade
    urns: Tuple[Tuple[int, ...], Tuple[int, ...]]   # balls of each colour
    copies: Tuple[int, int]                         # urns of each kind
    drawn: List[int]
    log_odds: float                                 # left over right
    question: str
    choices: Tuple[str, ...]
    answer: int


def likelihood(urn: Tuple[int, ...], drawn: List[int], replace: bool) -> float:
    left = list(urn)
    total = sum(left)
    p = 1.0
    for c in drawn:
        if left[c] <= 0 or total <= 0:
            return 0.0
        p *= left[c] / total
        if not replace:
            left[c] -= 1
            total -= 1
    return p


def odds(urns, copies, drawn, replace) -> float:
    a = copies[0] * likelihood(urns[0], drawn, replace)
    b = copies[1] * likelihood(urns[1], drawn, replace)
    if a <= 0 and b <= 0:
        return 0.0
    if b <= 0:
        return float('inf')
    if a <= 0:
        return float('-inf')
    return math.log(a / b)


def solve(p: Puzzle) -> int:
    lo = odds(p.urns, p.copies, p.drawn, p.level.replace)
    return LEFT if lo > 0 else RIGHT


def _urn(level: Grade, draw: random.Random, lean: int) -> Tuple[int, ...]:
    n = draw.randint(*level.size)
    if level.rung < 4:
        share = [1] * level.colours
        share[lean] = n - (level.colours - 1)
    else:
        share = [1] * level.colours
        for _k in range(n - level.colours):
            c = lean if draw.random() < 0.55 else draw.randrange(level.colours)
            share[c] += 1
    return tuple(share)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    want = draw.choice((LEFT, RIGHT))
    for _attempt in range(5000):
        leans = draw.sample(range(level.colours), 2)
        urns = (_urn(level, draw, leans[0]), _urn(level, draw, leans[1]))
        if urns[0] == urns[1]:
            continue
        copies = (1, 1)
        if level.priors:
            big = draw.choice((2, 3, 4))
            copies = (big, 1) if draw.random() < 0.5 else (1, big)
        k = draw.randint(*level.draws)
        pick = draw.random() * sum(copies) < copies[0]
        urn = list(urns[0 if pick else 1])
        drawn = []
        for _k in range(k):
            if sum(urn) <= 0:
                break
            x = draw.random() * sum(urn)
            c = 0
            while x >= urn[c]:
                x -= urn[c]
                c += 1
            drawn.append(c)
            if not level.replace:
                urn[c] -= 1
        lo = odds(urns, copies, drawn, level.replace)
        if abs(lo) < level.margin or math.isinf(lo) and level.rung >= 4:
            continue
        answer = LEFT if lo > 0 else RIGHT
        if answer != want:
            continue
        return Puzzle(level, urns, copies, drawn, lo,
                      _('From which kind of urn were these drawn, more '
                        'likely?'), (_('Left kind'), _('Right kind')), answer)
    raise RuntimeError('no urns for rung %d' % rung)
