# -*- coding: utf-8 -*-
"""Figures of Speech: what words mean when they do not mean what they say.

Questions from BIG-bench (see :mod:`neural_workshop.socialdata`):

* rungs 1-3: a sentence with a metaphor, and the plain words for it;
* rungs 4-6: those, and naming the figure of speech a sentence uses
  (simile, metaphor, personification, hyperbole...);
* rungs 7-9: those, and the moral of a fable;
* rungs 10 and up: those, and which sentence is not a metaphor of the
  kind the others are; more figures to choose from, less time to read.

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

TITLES = {'metaphor': _('A metaphor'), 'figure': _('A sentence'),
          'fable': _('A fable'), 'odd_metaphor': _('Which is the odd one?')}


class Grade(NamedTuple):
    rung: int
    kinds: tuple
    pace: Q.Pace
    figures: int               # figures of speech to choose among
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = ('metaphor',) + (('figure',) if r >= 4 else ()) + \
        (('fable',) if r >= 7 else ()) + (('odd_metaphor',) if r >= 10
                                          else ())
    figures = 4 if r < 7 else 6 if r < 10 else 8
    return Grade(r, kinds, Q.pace(r, slow=2.0, fast=4.0, base=6.0,
                                  floor=3.0), figures, 10, 0.7)


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    pools = {k: Q.deck(D.of(k), draw) for k in level.kinds}

    def make(kind):
        q = pools[kind]()
        if q is None:
            return None
        most = level.figures if kind == 'figure' else None
        return Q.item(q.prompt, [Q.step(_(q.ask), q.options, q.answer, draw,
                                        most=most)],
                      level.pace, title=TITLES[kind])

    items = Q.mixed(level.kinds, level.items, draw, make)
    if len(items) < level.items:
        return None
    return Q.assemble(level, items, level.skill)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
