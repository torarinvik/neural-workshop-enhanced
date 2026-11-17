# -*- coding: utf-8 -*-
"""Between the Lines: what someone means, not what they say.

Questions from BIG-bench (see :mod:`neural_workshop.socialdata`):

* rungs 1-3: an indirect answer -- "Are you coming?" "I have an exam at
  eight." -- does it mean yes or no?
* rungs 4-6: those, and which of two remarks is sarcastic;
* rungs 7-9: those, and whether a sentence is ironic;
* rungs 10 and up: all three mixed, with less and less time to read.

Every question has two answers, so a round has twenty and needs
fifteen: a guesser passes no more than one round in thirty, and saying
"yes" to everything never passes.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import NamedTuple, Optional

from . import feelings as F
from . import hand as H
from . import quiz as Q
from . import socialdata as D
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run

TITLES = {'implicature': _('What does B mean?'),
          'sarcasm': _('Two remarks'), 'irony': _('A sentence')}


class Grade(NamedTuple):
    rung: int
    kinds: tuple
    pace: Q.Pace
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = ('implicature',) + (('sarcasm',) if r >= 4 else ()) + \
        (('irony',) if r >= 7 else ())
    return Grade(r, kinds, Q.pace(r, slow=2.0, fast=4.5, base=5.0,
                                  floor=2.0), 20, 0.75)


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    pools = {k: Q.deck(D.of(k), draw) for k in level.kinds}

    def make(kind):
        q = pools[kind]()
        if q is None:
            return None
        return Q.item(q.prompt, [Q.step(_(q.ask), q.options, q.answer, draw,
                                        keep_order=True)],
                      level.pace, title=TITLES[kind])

    items = Q.mixed(level.kinds, level.items, draw, make)
    if len(items) < level.items:
        return None
    return Q.assemble(level, items, level.skill)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
