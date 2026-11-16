# -*- coding: utf-8 -*-
"""Reading People: how does she feel, why, and what should he do?

Short scenarios from EmoBench (see :mod:`neural_workshop.emotiondata`).
Some ask what their subject feels and then why; others ask what the
most helpful thing to do would be. The right answers are EmoBench's.

* rungs 1-3: what the subject feels;
* rungs 4-6: what they feel, and then why;
* rungs 7-9: what would be the most helpful thing to do;
* rungs 10+: all of these mixed, with less time to read each rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import NamedTuple, Optional

from . import emotiondata as D
from . import feelings as F
from . import hand as H
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run


class Grade(NamedTuple):
    rung: int
    kinds: tuple               # 'feel', 'why', 'act'
    seconds: float
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = (('feel',) if r < 4 else ('why',) if r < 7 else ('act',)
             if r < 10 else ('feel', 'why', 'act'))
    seconds = max(15.0, 45.0 - 2.0 * (r - 1))
    return Grade(r, kinds, seconds, 6, 0.67)


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    stories = list(D.stories())
    stories = stories * max(1, -(-60 // len(stories)))
    draw.shuffle(stories)
    items = []
    worst = 0.0
    for s in stories:
        if len(items) >= 6:
            break
        kind = draw.choice(level.kinds)
        if kind in ('feel', 'why') and s.kind != 'understand':
            continue
        if kind == 'act' and s.kind != 'act':
            continue
        if kind == 'act':
            steps = (F.Step(_('What would be most helpful for %s to do?') %
                            s.subject, s.choices,
                            s.choices.index(s.answer)),)
            truth = s.answer
        else:
            steps = (F.Step(_('How does %s feel?') % s.subject, s.choices,
                            s.choices.index(s.answer)),)
            truth = s.answer
            if kind == 'why':
                steps += (F.Step(_('Why?'), s.causes,
                                 s.causes.index(s.cause)),)
                truth += ': ' + s.cause
        chance = 1.0
        for st in steps:
            chance /= len(st.options)
        worst = max(worst, chance)
        items.append(F.Item(s.scenario, steps,
                            level.seconds * len(steps), truth=truth,
                            title=_('A story')))
    if len(items) < 6:
        return None
    need = max(F.need_for(6, worst),
               int(math.ceil(level.skill * 6)))
    return F.Round(level, tuple(items), need)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
