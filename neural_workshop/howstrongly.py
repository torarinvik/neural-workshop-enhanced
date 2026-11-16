# -*- coding: utf-8 -*-
"""How Strongly: how much does this character feel each emotion?

A short dialogue from EQ-Bench (see :mod:`neural_workshop.emotiondata`)
and four emotions; the reference is how strongly the character feels
each one at the end, from 0 to 10, as EQ-Bench's authors scored it.

* rungs 1-3: which of the four is felt most;
* rungs 4+: how strongly each is felt, on a scale of 0, 2, 4, 6, 8, 10.
  The four answers together may be off from the reference by no more
  than the rung allows: 8 points at rung 4, two fewer every two rungs,
  down to none at rung 11; the dialogues given are ones where giving the same
  answer to all four would not pass;
* the time to read and answer shortens with every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
from typing import NamedTuple, Optional

from . import emotiondata as D
from . import feelings as F
from . import hand as H
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run
SCALE = (0, 2, 4, 6, 8, 10)


class Grade(NamedTuple):
    rung: int
    strongest: bool
    tolerance: float
    seconds: float
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    tol = max(0.0, 8.0 - 2.0 * ((r - 3) // 2)) if r >= 4 else 0.0
    seconds = max(20.0, 60.0 - 2.0 * (r - 1))
    return Grade(r, r < 4, tol, seconds, 8 if r < 4 else 6,
                 0.75 if r < 4 else 0.67)


def _nearest(v: int) -> int:
    return min(range(len(SCALE)), key=lambda k: (abs(SCALE[k] - v), k))


def _chance(steps, tol) -> float:
    """How often answering at random comes within *tol*."""
    hits = total = 0
    for picks in itertools.product(range(len(SCALE)), repeat=len(steps)):
        total += 1
        err = sum(abs(SCALE[p] - SCALE[s.answer]) for s, p in
                  zip(steps, picks))
        hits += err <= tol
    return hits / total


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    pool = list(D.dialogues())
    pool = pool * max(1, -(-30 // len(pool)))   # few: may come round again
    draw.shuffle(pool)
    items, worst = [], 0.0
    for d in pool:
        if len(items) >= level.items:
            break
        text = d.text
        if level.strongest:
            top = max(d.scores)
            if sorted(d.scores)[-2] > top - 2:
                continue
            k = d.scores.index(top)
            items.append(F.Item(
                text, (F.Step(_('At the end, what does %s feel most?') %
                              d.who, d.emotions, k),),
                level.seconds, truth=d.emotions[k], title=_('A dialogue')))
            continue
        steps = tuple(F.Step(_('How strongly does %s feel: %s?') %
                             (d.who, e), tuple(str(v) for v in SCALE),
                             _nearest(s), tuple(float(v) for v in SCALE))
                      for e, s in zip(d.emotions, d.scores))
        # No one answer given to all four may pass: not all 0, not all 4.
        if any(sum(abs(c - SCALE[s.answer]) for s in steps) <=
               level.tolerance for c in SCALE):
            continue
        worst = max(worst, _chance(steps, level.tolerance))
        truth = ', '.join('%s %d' % (e, SCALE[s.answer])
                          for e, s in zip(d.emotions, steps))
        items.append(F.Item(text, steps, level.seconds, truth=truth,
                            tolerance=level.tolerance,
                            title=_('A dialogue')))
    if len(items) < level.items:
        return None
    chance = 0.25 if level.strongest else worst
    need = max(F.need_for(level.items, chance),
               int(math.ceil(level.skill * level.items)))
    return F.Round(level, tuple(items), need)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
