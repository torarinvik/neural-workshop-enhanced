# -*- coding: utf-8 -*-
"""Which Feeling: what does the writer of this comment feel?

Short comments from Reddit, each labelled by the raters of GoEmotions
with one emotion of 27 (or neutral); see
:mod:`neural_workshop.emotiondata`. The right answer is theirs.

The ladder is about how close the other answers are:

* rungs 1-2: two answers of opposite feeling (joy or anger);
* rungs 3-4: three, one of them neither good nor bad (surprise,
  curiosity, confusion);
* rungs 5-7: four, one of them a near neighbour of the right one;
* rungs 8-10: four, all of the same kind (anger, annoyance,
  disapproval, disgust);
* rungs 11-13: six of the same kind, and neutral;
* rungs 14+: eight, and less time to read, without end.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import emotiondata as D
from . import feelings as F
from . import hand as H
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play, Run = F.act, F.autopilot, F.play, F.Run

GOOD = ('admiration', 'amusement', 'approval', 'caring', 'desire',
        'excitement', 'gratitude', 'joy', 'love', 'optimism', 'pride',
        'relief')
BAD = ('anger', 'annoyance', 'disappointment', 'disapproval', 'disgust',
       'embarrassment', 'fear', 'grief', 'nervousness', 'remorse', 'sadness')
OPEN = ('confusion', 'curiosity', 'realization', 'surprise')
PLAIN = ('joy', 'gratitude', 'love', 'amusement', 'anger', 'sadness',
         'fear', 'disgust')


def kind_of(label: str) -> Tuple[str, ...]:
    return GOOD if label in GOOD else BAD if label in BAD else OPEN


class Grade(NamedTuple):
    rung: int
    options: int
    near: int                  # distractors of the same kind
    neutral: bool
    plain: bool                # the right answer is a plain emotion
    seconds: float
    items: int
    skill: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    options = 2 if r < 3 else 3 if r < 5 else 4 if r < 11 else \
        6 if r < 14 else 8
    near = 0 if r < 5 else 1 if r < 8 else options - 1
    seconds = max(4.0, 16.0 - 0.6 * (r - 1))
    skill = 0.8 if r < 8 else 0.7 if r < 11 else 0.6
    return Grade(r, options, near, r >= 11, r < 5, round(seconds, 1), 10,
                 skill)


def _by_label() -> Dict[str, List[D.Comment]]:
    out: Dict[str, List[D.Comment]] = {}
    for c in D.comments():
        out.setdefault(c.label, []).append(c)
    return out


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    by = _by_label()
    labels = [l for l in (PLAIN if level.plain else GOOD + BAD + OPEN)
              if l in by]
    if level.neutral and 'neutral' in by:
        labels.append('neutral')
    if not labels:
        return None
    items = []
    for _k in range(level.items):
        truth = draw.choice(labels)
        c = draw.choice(by[truth])
        if truth == 'neutral':
            same = [l for l in GOOD + BAD + OPEN]
        else:
            same = [l for l in kind_of(truth) if l != truth]
        far = [l for l in GOOD + BAD + OPEN
               if l != truth and l not in kind_of(truth)]
        if level.near >= level.options - 1:
            pool = same + (['neutral'] if level.neutral and
                           truth != 'neutral' else [])
            draw.shuffle(pool)
            others = pool[:level.options - 1]
        else:
            draw.shuffle(same)
            draw.shuffle(far)
            others = same[:level.near]
            if level.options >= 3 and truth not in OPEN:
                opens = [l for l in OPEN if l not in others]
                others.append(draw.choice(opens))
            others += [l for l in far if l not in others][
                :level.options - 1 - len(others)]
        if len(others) < level.options - 1:
            return None
        opts = others[:level.options - 1] + [truth]
        draw.shuffle(opts)
        items.append(F.Item(
            '“%s”' % c.text,
            (F.Step(_('What does the writer feel?'), tuple(opts),
                    opts.index(truth)),),
            level.seconds, truth=truth,
            title=_('A comment')))
    need = max(F.need_for(level.items, 1.0 / level.options),
               int(math.ceil(level.skill * level.items)))
    return F.Round(level, tuple(items), need)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
