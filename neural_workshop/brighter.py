# -*- coding: utf-8 -*-
"""Brighter: which patch is the lighter?

Grey patches, each on its own surround. Which patch is lighter -- the
patch itself, whatever it sits on? A grey looks lighter on a dark
ground and darker on a light one (simultaneous contrast), so from rung
4 the surrounds are dealt to argue against the truth: the lighter patch
sits on the lighter ground.

The ladder:

* rungs 1-3: two patches on like grounds, far apart in lightness;
* rungs 4-6: the grounds differ, and mislead;
* rungs 7-9: closer greys; the grounds are gradients;
* rungs 10-12: patches of different sizes;
* from rung 13: three patches, then four, and the step between them
  narrowing toward one part in a hundred.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _


class Grade(NamedTuple):
    rung: int
    patches: int
    step: float          # lightness between the lightest and the next
    mislead: bool
    gradient: bool
    sizes: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        patches=2 if r < 13 else 3 if r < 19 else 4,
        step=(0.2 if r < 4 else 0.14 if r < 7 else 0.09 if r < 10
              else 0.06 if r < 13 else max(0.01, 0.05 - 0.002 * (r - 13))),
        mislead=r >= 4,
        gradient=r >= 7,
        sizes=r >= 10)


class Puzzle(NamedTuple):
    level: Grade
    values: List[float]          # each patch's lightness
    grounds: List[float]         # each surround's
    sizes: List[float]
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> int:
    return p.values.index(max(p.values))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.patches
    top = draw.uniform(0.45, 0.7)
    values = [top - level.step * draw.uniform(1.0, 1.6) for _k in range(n)]
    answer = S.slot(seed, n)
    values[answer] = top
    if level.mislead:
        # The lighter the patch, the lighter its ground.
        grounds = [0.25 + 0.6 * (v - min(values)) / max(1e-9, top - min(values))
                   + draw.uniform(-0.04, 0.04) for v in values]
    else:
        g = draw.choice((0.15, 0.9))
        grounds = [g] * n
    sizes = [draw.uniform(0.6, 1.0) if level.sizes else 0.8 for _k in range(n)]
    names = (_('Left'), _('Right')) if n == 2 else \
        tuple(str(k + 1) for k in range(n))
    return Puzzle(level, values, grounds, sizes, draw.random(),
                  draw.choice(S.PAPERS), _('Which patch is the lighter?'),
                  names, answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    n = len(p.values)
    w = S.W / n
    for k in range(n):
        x = k * w
        g = p.grounds[k]
        if p.level.gradient:
            bands = 16
            for b in range(bands):
                v = g + (b / (bands - 1.0) - 0.5) * 0.25 * (1 if k % 2 else -1)
                out.append(S.rect(x + 0.02, 0.04 + b * 0.92 / bands,
                                  w - 0.04, 0.92 / bands + 0.002,
                                  S.grey(v, 0.06, p.hue)))
        else:
            out.append(S.rect(x + 0.02, 0.04, w - 0.04, 0.92,
                              S.grey(g, 0.06, p.hue)))
        side = 0.3 * p.sizes[k]
        out.append(S.rect(x + w / 2 - side / 2, 0.5 - side / 2, side, side,
                          S.grey(p.values[k], 0.06, p.hue)))
        out.append(S.hit(x + 0.02, 0.04, w - 0.04, 0.92, k))
    return out
