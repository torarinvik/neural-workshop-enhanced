# -*- coding: utf-8 -*-
"""A wait of uneven length: a cue, then a wait drawn anew each trial,
then the question.

In the looking-back tasks the cue lies a fixed number of frames back at
each rung, so a learner can learn to look exactly that far back. Here
the wait is drawn evenly each trial from k to 3k frames at rung k, so
no fixed distance back is right more often than another.

``uneven``  one of four places lights for a frame; then 1k to 3k frames
            with nothing showing; then press the place that lit. Any
            press before the question is put ends the trial unpaid (see
            :mod:`keptcue`).

The wait is drawn apart from the cue, so the trial's length says
nothing of the answer: the question frame, and the length of the wait
with it, are at one in four. The tests count it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional, Tuple

from . import framed, keptcue
from .i18n import _
from .keptcue import PLACES, Run, act  # noqa: F401

KINDS = ('uneven',)
QUESTION = _('Which place lit up?')


def waits(rung: int) -> Tuple[int, int]:
    """The shortest and the longest wait at *rung*, in frames."""
    k = max(1, int(rung))
    return k, 3 * k


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    if kind not in KINDS:
        raise ValueError(kind)
    k = max(1, int(rung))
    cue = rng.randrange(PLACES)
    wait = rng.randint(*waits(k))
    return keptcue.make(kind, k, rng, look, ((0, cue, 0),), wait + 2, cue,
                        QUESTION, wait=wait)
