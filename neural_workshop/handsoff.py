# -*- coding: utf-8 -*-
"""Hands off: a cue, a wait with nothing of it showing, then the
question -- with the wait closed to presses (see :mod:`keptcue`).

``still``  one of four places lights for a frame; k frames go by with
           nothing showing; then press the place that lit. Any press
           before the question is put ends the trial unpaid.
``busy``   one of four places lights for a frame; then k jobs, each
           two frames long: a dot lights in one of the places, and its
           port must be pressed once while it shows. A wrong press, a
           second press, a press outside a job, or a job left undone
           ends the trial unpaid. Then press the place that lit. The
           wait is 2k frames, and the shortest way is k + 1 presses.

Where the cue lights is drawn evenly; where each dot lights is drawn
evenly too, apart from the cue, so a learner's presses during the wait
are fixed by the jobs and cannot carry the cue. The question frame
shows the four places and a question mark, the same whatever the
answer: from it alone, one in four. The tests count both.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, keptcue
from .i18n import _
from .keptcue import JOB, PLACES, Run, act  # noqa: F401

KINDS = ('still', 'busy')
QUESTION = _('Which place lit up?')


def wait(kind: str, rung: int) -> int:
    """Frames between the cue and the question."""
    k = max(1, int(rung))
    return JOB * k if kind == 'busy' else k


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0) -> framed.Puzzle:
    rng = rng or random.Random()
    if kind not in KINDS:
        raise ValueError(kind)
    k = max(1, int(rung))
    cue = rng.randrange(PLACES)
    jobs = ()
    if kind == 'busy':
        jobs = tuple((1 + JOB * j, rng.randrange(PLACES))
                     for j in range(k))
    return keptcue.make(kind, k, rng, look, ((0, cue, 0),),
                        wait(kind, k) + 2, cue, QUESTION,
                        early='jobs' if kind == 'busy' else 'end',
                        jobs=jobs)
