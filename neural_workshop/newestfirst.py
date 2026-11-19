# -*- coding: utf-8 -*-
"""The newest counts, or the first counts: a cue, and in some trials
later cues of the same look elsewhere.

A place lights for a frame. Then come k slots, every other frame; each
slot holds a later cue or nothing, how many of them drawn evenly from
none to k, each at a place other than the cue before it. A frame with
nothing showing follows the last slot, and then the question:

``newest``  press the place that lit last;
``first``   press the place that lit first: the later ones are decoys.

Rung k is k slots, so up to k later cues; the trial is 2k + 3 frames
long whatever came, so its length says nothing. Any press before the
question is put ends the trial unpaid (see :mod:`keptcue`).

The question frame is at one in four. Answering with the other rule
earns what the tests count: on the newest, pressing where the first cue
was is right about one time in two at rung 1, since there no later cue
comes half the time; and the same holds the other way round.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, keptcue
from .i18n import _
from .keptcue import PLACES, Run, act  # noqa: F401

KINDS = ('newest', 'first')
QUESTIONS = {'newest': _('Where did one light last?'),
             'first': _('Where did one light first?')}


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    if kind not in KINDS:
        raise ValueError(kind)
    k = max(1, int(rung))
    later = rng.randint(0, k)
    slots = sorted(rng.sample(range(k), later))
    place = rng.randrange(PLACES)
    shown = [(0, place, 0)]
    for slot in slots:
        place = rng.choice([q for q in range(PLACES) if q != place])
        shown.append((2 + 2 * slot, place, 0))
    answer = shown[-1][1] if kind == 'newest' else shown[0][1]
    return keptcue.make(kind, k, rng, look, shown, 2 * k + 3, answer,
                        QUESTIONS[kind], later=later)
