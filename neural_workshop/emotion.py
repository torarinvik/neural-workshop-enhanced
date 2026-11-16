# -*- coding: utf-8 -*-
"""Emotion: which emotion is this face showing?

A face is shown, and the emotion it shows is picked from the buttons
below it. The faces are photographs from FER-2013, each read by ten
people for FERPlus (see :mod:`neural_workshop.emotiondata`); the right
answer is what most of them said, and how many of them said it is how
plain the face is. Without the photographs, faces drawn from a few
lines stand in.

The ladder:

* rung 1: happy or sad, on faces nearly everyone read the same way;
* rung 2: surprise too; rung 3: anger and a neutral face;
* rung 4: all seven of fear, disgust and the rest; rung 6: contempt;
* rungs 4+: faces fewer people agreed on, down to half of them;
* rungs 8+: the face is shown for a moment and then covered;
* rungs 10+: only the eyes, or only the mouth, of some faces;
* rungs 14+: faces with two emotions in them: name the stronger, then
  the other;
* above that the faces get subtler and the moment shorter without end.

A round is twelve faces; it passes with enough right that guessing
would almost never do it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import emotiondata as D
from . import feelings as F
from .i18n import _

PORTS, EVENTS, PATCHES = F.PORTS, F.EVENTS, F.PATCHES
act, autopilot, play = F.act, F.autopilot, F.play
Run = F.Run
NAMES = {'neutral': 'neutral', 'happiness': 'happy', 'surprise': 'surprised',
         'sadness': 'sad', 'anger': 'angry', 'disgust': 'disgusted',
         'fear': 'afraid', 'contempt': 'contemptuous'}
ORDER = ('happiness', 'sadness', 'surprise', 'anger', 'neutral', 'fear',
         'disgust', 'contempt')


class Grade(NamedTuple):
    rung: int
    options: Tuple[str, ...]
    agree: Tuple[float, float]     # how plain the faces are
    flash: float                   # 0: the face stays
    crop: float                    # share of faces cut to eyes or mouth
    two: bool                      # name the stronger, then the other
    seconds: float
    faces: int
    skill: float                   # the share a reader should get


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    n = 2 if r < 2 else 3 if r < 3 else 5 if r < 4 else 7 if r < 6 else 8
    lo = 0.9 if r < 4 else 0.8 if r < 6 else 0.7 if r < 9 else \
        0.6 if r < 12 else max(0.4, 0.6 - 0.02 * (r - 11))
    hi = 1.0 if r < 9 else lo + 0.25
    flash = 0.0 if r < 8 else max(0.15, 1.6 - 0.12 * (r - 8))
    crop = 0.0 if r < 10 else min(0.6, 0.3 + 0.03 * (r - 10))
    seconds = max(2.5, 10.0 - 0.35 * (r - 1))
    skill = 0.8 if r < 4 else 0.75 if r < 9 else 0.65 if r < 14 else 0.5
    return Grade(r, ORDER[:n], (lo, hi), round(flash, 2), round(crop, 2),
                 r >= 14, round(seconds, 2), 12, skill)


def _pool(level: Grade, two: bool):
    lo, hi = level.agree
    keep = {e: [] for e in level.options}
    idx = {e: D.EMOTIONS.index(e) for e in level.options}
    for f in D.faces():
        top = f.top()
        if top is None or D.EMOTIONS[top] not in keep:
            continue
        a = f.agreement()
        if two:
            r = f.ranked()
            second = r[1]
            if D.EMOTIONS[second] not in keep or f.votes[second] < \
                    0.25 * f.total() or f.votes[second] == f.votes[r[2]]:
                continue
        elif not lo <= a <= hi:
            continue
        keep[D.EMOTIONS[top]].append(f)
    del idx
    return {e: fs for e, fs in keep.items() if fs}


def build(level: Grade, draw: random.Random) -> Optional[F.Round]:
    pool = _pool(level, level.two)
    if len(pool) < 2:
        pool = _pool(level._replace(agree=(0.5, 1.0)), level.two)
    if len(pool) < 2:
        return None
    labels = [NAMES[e] for e in level.options]
    items: List[F.Item] = []
    used = set()
    for _k in range(level.faces):
        emo = draw.choice(sorted(pool))
        face = draw.choice(pool[emo])
        if (face.key, face.drawn) in used and len(pool[emo]) > 1:
            face = draw.choice(pool[emo])
        used.add((face.key, face.drawn))
        crop = ''
        if level.crop and draw.random() < level.crop:
            crop = draw.choice(('eyes', 'mouth'))
        steps = [F.Step(_('Which emotion is this?') if not level.two else
                        _('Which emotion is strongest?'), tuple(labels),
                        level.options.index(emo))]
        truth = NAMES[emo]
        if level.two:
            second = D.EMOTIONS[face.ranked()[1]]
            steps.append(F.Step(_('And the next strongest?'), tuple(labels),
                                level.options.index(second)))
            truth += _(', then ') + NAMES[second]
        items.append(F.Item('', tuple(steps), level.seconds * len(steps),
                            face=face, flash=level.flash, crop=crop,
                            truth=truth))
    chance = 1.0 / len(labels) ** (2 if level.two else 1)
    # Guessing, or naming one emotion every time, almost never passes.
    need = max(F.need_for(level.faces, chance),
               F.need_for(level.faces, 1.0 / len(pool)) if not level.two
               else 0,
               int(math.ceil(level.skill * level.faces)))
    return F.Round(level, tuple(items), need)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> F.Round:
    import sys
    from . import hand as H
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=40)
