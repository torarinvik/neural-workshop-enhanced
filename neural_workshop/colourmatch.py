# -*- coding: utf-8 -*-
"""Colour Match: which swatch is the same colour as the sample?

A sample colour and a row of swatches; exactly one is the sample's
colour, the others a step away in hue, in strength or in lightness.
From rung 4 every swatch sits on a ground of its own colour, which
pushes how it looks; from rung 10 the swatches differ in shape and size
too. The match is of the colour itself.

The ladder:

* rungs 1-3: three swatches, the others a long way off;
* rungs 4-6: four, on coloured grounds;
* rungs 7-9: closer;
* rungs 10-12: different shapes and sizes;
* from rung 13: five swatches, then six, the step narrowing every
  rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _


class Grade(NamedTuple):
    rung: int
    swatches: int
    step: float          # how far the others are, 1 a long way
    grounds: bool
    shapes: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        swatches=3 if r < 4 else 4 if r < 13 else 5 if r < 19 else 6,
        step=(1.0 if r < 4 else 0.7 if r < 7 else 0.45 if r < 10
              else 0.35 if r < 13 else max(0.06, 0.3 * 0.9 ** (r - 13))),
        grounds=r >= 4,
        shapes=r >= 10)


HSV = Tuple[float, float, float]


class Puzzle(NamedTuple):
    level: Grade
    sample: HSV
    swatches: List[HSV]
    grounds: List[HSV]
    kinds: List[int]             # 0 square, 1 disc
    sizes: List[float]
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> Optional[int]:
    hits = [k for k, c in enumerate(p.swatches) if S.hsv(*c) == S.hsv(*p.sample)]
    return hits[0] if len(hits) == 1 else None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.swatches
    for _attempt in range(200):
        sample = (draw.random(), draw.uniform(0.45, 0.8), draw.uniform(0.55, 0.85))
        others: List[HSV] = []
        for k in range(n - 1):
            h, s, v = sample
            which = draw.choice('hsv')
            sign = draw.choice((-1, 1)) * (1 + 0.5 * (k // 2))
            if which == 'h':
                h += 0.16 * level.step * sign
            elif which == 's':
                s = max(0.1, min(1.0, s + 0.4 * level.step * sign))
            else:
                v = max(0.2, min(1.0, v + 0.35 * level.step * sign))
            others.append((h, s, v))
        answer = S.slot(seed, n)
        others.insert(answer, sample)
        if len({S.hsv(*c) for c in others}) < n:
            continue
        grounds = [(draw.random(), draw.uniform(0.3, 0.7), draw.uniform(0.3, 0.9))
                   if level.grounds else (0.0, 0.0, 0.93) for _k in range(n)]
        p = Puzzle(level, sample, others, grounds,
                   [draw.randrange(2) if level.shapes else 0 for _k in range(n)],
                   [draw.uniform(0.6, 1.0) if level.shapes else 0.85
                    for _k in range(n)],
                   draw.choice(S.PAPERS),
                   _('Which swatch is the same colour as the sample?'),
                   tuple(str(k + 1) for k in range(n)), answer)
        if solve(p) == answer:
            return p
    raise RuntimeError('no colours for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = [S.rect(S.W / 2 - 0.16, 0.64, 0.32, 0.3, S.hsv(*p.sample)),
           S.text(S.W / 2 - 0.3, 0.79, 0.045, _('sample'))]
    n = len(p.swatches)
    w = S.W / n
    for k in range(n):
        x = k * w
        out.append(S.rect(x + 0.015, 0.05, w - 0.03, 0.5, S.hsv(*p.grounds[k])))
        side = min(w * 0.55, 0.3) * p.sizes[k]
        cx, cy = x + w / 2, 0.3
        if p.kinds[k]:
            out.append(S.disc(cx, cy, side / 2, S.hsv(*p.swatches[k])))
        else:
            out.append(S.rect(cx - side / 2, cy - side / 2, side, side,
                              S.hsv(*p.swatches[k])))
        out.append(S.hit(x + 0.015, 0.05, w - 0.03, 0.5, k))
    return out
