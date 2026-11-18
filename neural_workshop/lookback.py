# -*- coding: utf-8 -*-
"""Looking back: the answer is in a frame that is no longer showing.

A trial is a short run of frames, one after another, and then a
question about the frame *k* back from the one now showing, where k is
the rung. At rung 1 the frame needed is the one just before the
present; each rung puts it one frame further back.

``shape``  a shape a frame: press the port for the shape k frames ago
``cue``    one of four squares lights, then nothing shows for k frames:
           press the port for the square that lit
``sound``  a tone a frame, low, middle or high: press the port for the
           tone k frames ago

Presses before the question is put are ignored; a wrong press once it
is put ends the trial.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Any, Dict, NamedTuple, Optional, Tuple

from . import showing
from .i18n import _

#: Seconds from one frame to the next, and how long a frame shows.
FRAME, SHOWN = 0.5, 0.38
#: Seconds to answer once the question is put.
ANSWER = 4.0
SHAPES = ('circle', 'square', 'triangle', 'diamond', 'star', 'cross')
HUES = ((36, 104, 196), (122, 70, 170), (20, 124, 132), (176, 110, 20),
        (150, 70, 110))
BANDS = (196.0, 392.0, 784.0)            # low, middle, high
VOICES = ('sine', 'flute', 'organ', 'clarinet')
KINDS = ('shape', 'cue', 'sound')


class Puzzle(NamedTuple):
    kind: str
    back: int                    # k: how many frames back the answer is
    frames: Tuple[int, ...]      # what each frame held
    choices: Tuple[str, ...]
    answer: int
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    data: Dict[str, Any]
    question: str


def deal(kind: str, rung: int,
         rng: Optional[random.Random] = None) -> Puzzle:
    rng = rng or random.Random()
    k = max(1, int(rung))
    hue = rng.randrange(len(HUES))
    notes: tuple = ()
    patches: tuple = ()
    if kind == 'cue':
        cell = rng.randrange(4)
        frames = (cell,) + (-1,) * k
        choices = ('1', '2', '3', '4')
        answer = cell
        data = {'hue': hue, 'layout': rng.choice(('row', 'column', 'square'))}
        question = _('Which square lit up?')
    else:
        frames = [rng.randrange(3) for _f in range(k + 1)]
        # Now is not then: the frame showing is never the answer.
        frames[k] = rng.choice([s for s in range(3) if s != frames[0]])
        frames = tuple(frames)
        if kind == 'shape':
            cards = [0, 1, 2]
            rng.shuffle(cards)               # cards[port] = the shape on it
            choices = ('1', '2', '3')
            answer = cards.index(frames[0])
            data = {'hue': hue, 'kinds': rng.sample(SHAPES, 3),
                    'cards': cards,
                    'spots': [(rng.uniform(0.2, 0.8), rng.uniform(0.25, 0.75))
                              for _f in frames]}
            question = (_('Which shape was showing one frame ago?') if k == 1
                        else _('Which shape was showing %d frames ago?') % k)
        else:
            choices = (_('low'), _('middle'), _('high'))
            answer = frames[0]
            bend = rng.uniform(-1.5, 1.5)
            seed = rng.randrange(1, 10 ** 6)
            patches = (showing.patch(rng.choice(VOICES), seed),)
            notes = tuple(
                showing.note(f * FRAME, SHOWN * 0.8,
                             showing.semitones(BANDS[band],
                                               bend + rng.uniform(-0.4, 0.4)))
                for f, band in enumerate(frames))
            data = {'hue': hue}
            question = (_('Which tone sounded one before this?') if k == 1
                        else _('Which tone sounded %d before this?') % k)
    # The cue's k hidden frames go by first; the others ask on the
    # frame k after the one wanted.
    open_at = (k + 1 if kind == 'cue' else k) * FRAME
    return Puzzle(kind, k, frames, choices, answer, open_at,
                  open_at + ANSWER, notes, patches, data, question)


def frame_at(puzzle: Puzzle, t: float) -> Tuple[int, bool]:
    """Which frame *t* falls in, and whether it is showing."""
    f = min(len(puzzle.frames) - 1, int(t / FRAME))
    last = f == len(puzzle.frames) - 1
    return f, last or t - f * FRAME < SHOWN
