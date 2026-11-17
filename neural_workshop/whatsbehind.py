# -*- coding: utf-8 -*-
"""What Is Behind: which whole shape is the one partly hidden?

A shape with a screen across it, so only parts of its outline show, and
below it some whole shapes. Exactly one of them is the hidden shape:
the others run a little differently, and so do not agree with the parts
that can be seen. The eye has to carry the outline on behind the screen
and compare.

The ladder:

* rungs 1-3: a third hidden; two shapes, quite unlike;
* rungs 4-6: two fifths hidden; three shapes;
* rungs 7-9: half hidden behind two screens; closer shapes;
* rungs 10-12: four shapes;
* from rung 13: the whole shapes are turned round, and closer to the
  true one every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

Outline = Tuple[Tuple[float, float], ...]


class Grade(NamedTuple):
    rung: int
    shapes: int
    hidden: float        # share of the width behind screens
    screens: int
    unlike: float        # how far the others run from the true one
    turned: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        shapes=2 if r < 4 else 3 if r < 10 else 4,
        hidden=0.33 if r < 4 else 0.4 if r < 7 else 0.5 if r < 13 else 0.55,
        screens=1 if r < 7 else 2,
        unlike=(0.3 if r < 4 else 0.2 if r < 7 else 0.14 if r < 10
                else 0.1 if r < 13 else max(0.035, 0.085 * 0.92 ** (r - 13))),
        turned=r >= 13)


class Puzzle(NamedTuple):
    level: Grade
    shape: Outline               # the hidden shape, reaching about 1
    screens: List[Tuple[float, float]]   # each (left, width), same units
    wholes: List[Outline]
    turns: List[float]
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def seen(p: Puzzle) -> List[int]:
    """Which points of the outline show."""
    return [k for k, (x, _y) in enumerate(p.shape)
            if not any(a <= x <= a + w for a, w in p.screens)]


def gap(p: Puzzle, whole: Outline) -> float:
    """How far *whole* runs from the parts that show."""
    return max(math.hypot(whole[k][0] - p.shape[k][0],
                          whole[k][1] - p.shape[k][1]) for k in seen(p))


def solve(p: Puzzle) -> int:
    gaps = [gap(p, w) for w in p.wholes]
    return gaps.index(min(gaps))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.shapes
    answer = S.slot(seed, n)
    for _attempt in range(300):
        shape = tuple(S.blob(draw, 4, 0.2, 72))
        xs = [x for x, _y in shape]
        lo, hi = min(xs), max(xs)
        width = (hi - lo) * level.hidden / level.screens
        if level.screens == 1:
            a = draw.uniform(lo + 0.15, hi - 0.15 - width)
            screens = [(a, width)]
        else:
            a = draw.uniform(lo + 0.1, lo + (hi - lo) / 2 - width - 0.05)
            b = draw.uniform(lo + (hi - lo) / 2 + 0.05, hi - 0.1 - width)
            screens = [(a, width), (b, width)]
        p = Puzzle(level, shape, screens, [], [], 0.0, S.PAPER, '', (), answer)
        wholes: List[Outline] = []
        for k in range(n):
            if k == answer:
                wholes.append(shape)
                continue
            for _try in range(40):
                other = tuple(S.bend(shape, level.unlike * draw.uniform(1.0, 1.3),
                                     draw))
                if gap(p, other) >= level.unlike * 0.8 and all(
                        max(math.hypot(o[0] - w[0], o[1] - w[1])
                            for o, w in zip(other, done)) >= level.unlike * 0.5
                        for done in wholes):
                    wholes.append(other)
                    break
        if len(wholes) < n:
            continue
        turns = [draw.uniform(0, 2 * math.pi) if level.turned else 0.0
                 for _k in range(n)]
        return p._replace(wholes=wholes, turns=turns, hue=draw.random(),
                          paper=draw.choice(S.PAPERS),
                          question=_('Which whole shape is the one behind '
                                     'the screen?'),
                          choices=tuple(str(k + 1) for k in range(n)))
    raise RuntimeError('no shapes for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    fill = S.hsv(p.hue, 0.55, 0.8)
    scale = 0.15
    cx, cy = S.W / 2, 0.74
    out = [S.poly(S.place(p.shape, cx, cy, scale), fill)]
    if not judged:
        for a, w in p.screens:
            out.append(S.rect(cx + a * scale, cy - 1.6 * scale, w * scale,
                              3.2 * scale, (120, 124, 135)))
    n = len(p.wholes)
    w = S.W / n
    for k, whole in enumerate(p.wholes):
        out.append(S.poly(S.place(whole, (k + 0.5) * w, 0.25, scale,
                                  p.turns[k]), fill))
        out.append(S.hit(k * w + 0.01, 0.02, w - 0.02, 0.46, k))
        out.append(S.text(k * w + 0.05, 0.44, 0.04, str(k + 1)))
    return out
