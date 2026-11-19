# -*- coding: utf-8 -*-
"""Several kept, one asked for: cues shown one after another, each in a
colour of its own, a wait, then a question that shows which is wanted.

``several``  two to four places light one after another, a frame each,
             each in its own colour and no place twice; two frames go by
             with nothing showing; then the question shows one of the
             colours: press the place that lit in it. Rung k shows k + 1
             cues, up to four; higher rungs play as rung 3. Any press
             before the question is put ends the trial unpaid (see
             :mod:`keptcue`).

Which cue is asked for is drawn evenly, and the colours are dealt to the
places at random, so the question frame -- the places and the colour
asked for -- is at one in four. Answering with the last cue shown earns
one in as many cues as were shown (a half at rung 1). The tests count
both.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, keptcue
from .i18n import _
from .keptcue import PLACES, Run, act  # noqa: F401

KINDS = ('several',)
#: Frames with nothing showing between the last cue and the question.
WAIT = 2
TOP = 3
QUESTION = _('Where was the one in this colour?')


def cues(rung: int) -> int:
    """How many cues show at *rung*."""
    return min(TOP, max(1, int(rung))) + 1


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    if kind not in KINDS:
        raise ValueError(kind)
    k = max(1, int(rung))
    n = cues(k)
    places = rng.sample(range(PLACES), n)
    colours = rng.sample(range(len(keptcue.COLOURS[look])), n)
    shown = tuple((f, places[f], colours[f]) for f in range(n))
    asked = rng.randrange(n)
    return keptcue.make(kind, k, rng, look, shown, n + WAIT + 1,
                        places[asked], QUESTION, asked=colours[asked],
                        which=asked)
