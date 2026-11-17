# -*- coding: utf-8 -*-
"""Social Sense: why people do what they do, and what comes of it.

Everyday situations from Social IQa (see :mod:`neural_workshop.socialdata`),
each with a question and three answers:

* rungs 1-3: how someone feels, or what they are like;
* rungs 4-6: those, and what they need first or will want next;
* rungs 7-9: those, and why they did it, how others feel, what happens;
* rungs 10-12: every kind of question, with less time to read;
* rungs 13 and up: two questions about the same situation, both to be
  right, and less time still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import random
from typing import Dict, NamedTuple, Optional, Tuple

from . import feelings as F
from . import hand as H
from . import quiz as Q
from . import socialdata as D
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run

LADDER = (('feel', 'describe'), ('want', 'need'),
          ('why', 'others_feel', 'happens'), ('next',))


class Grade(NamedTuple):
    rung: int
    kinds: tuple
    pace: Q.Pace
    items: int
    pairs: bool
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = sum(LADDER[:min(4, 1 + (r - 1) // 3)], ())
    return Grade(r, kinds, Q.pace(r, slow=2.2, fast=4.5, base=5.0,
                                  floor=2.0), 12, r >= 13, 0.7)


@functools.lru_cache(maxsize=1)
def _situations() -> Dict[str, Tuple[D.Question, ...]]:
    by: Dict[str, list] = {}
    for q in D.of('social'):
        by.setdefault(q.prompt, []).append(q)
    return {k: tuple(v) for k, v in by.items()
            if len({q.ask for q in v}) >= 2}


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    kinds = tuple(k for k in level.kinds if D.of('social:' + k))
    pools = {k: Q.deck(D.of('social:' + k), draw) for k in kinds}
    if not kinds:
        return None

    pairs = Q.deck(sorted(_situations().values()), draw)

    def make(kind):
        if level.pairs:
            pair = pairs()
            if pair is None:
                return None
            qs = list({o.ask: o for o in pair}.values())[:2]
            draw.shuffle(qs)
            q = qs[0]
        else:
            q = pools[kind]()
            if q is None:
                return None
            qs = [q]
        return Q.item(q.prompt, [Q.step(o.ask, o.options, o.answer, draw)
                                 for o in qs], level.pace,
                      title=_('A situation'))

    items = Q.mixed(kinds, level.items, draw, make)
    if len(items) < level.items:
        return None
    return Q.assemble(level, items, level.skill)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
