# -*- coding: utf-8 -*-
"""Cues kept over a wait, with the wait closed to presses: what the
hands-off families share.

In Hidden Cue and the far-cue tasks a press before the question is
ignored. A learner can use that: it presses a code during the wait and
reads its own presses back at the question, and needs no memory of the
cue. The tasks built on this module close that, in one of two ways a
task chooses (``data['early']``):

``end``   any press before the question is put ends the trial unpaid;
``jobs``  the wait is filled with small jobs, each :data:`JOB` frames
          long: a dot lights in one of the four places, and its port
          must be pressed once while it shows. A wrong press, a second
          press, a press outside a job, or a job left undone ends the
          trial unpaid. Where the dot lights is drawn at random, apart
          from the cue, so the presses a trial is played with say
          nothing of the cue.

A trial is a run of frames on the frame clock of :mod:`framed`: some
frames show a cue, a lit place, in a colour (``data['cues']``, as
``(frame, place, colour)``); the question is put on the last frame,
and the answer is a place. Four places, four ports. Two looks, as in
:mod:`framed`: look 0 draws squares in a row, a column or a square,
the ports in reading order; look 1 draws beads round a ring, the ports
the other way round.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional, Sequence, Tuple

from . import framed
from .framed import FRAME, GIVE
from .i18n import _

PLACES = 4
#: Frames a job lasts.
JOB = 2
LAYOUTS = ('row', 'column', 'square')
#: Cue colours by look: four a look, no colour shared between looks.
COLOURS = (((214, 48, 49), (30, 110, 220), (210, 160, 10), (40, 150, 70)),
           ((140, 70, 200), (240, 120, 180), (0, 176, 176), (40, 40, 40)))
EARLY = ('end', 'jobs')


def order(look: int) -> Tuple[int, ...]:
    """The place each port stands for."""
    return framed.port_order(look, PLACES)


def port_of(look: int, place: int) -> int:
    return order(look).index(place)


def make(kind: str, k: int, rng: random.Random, look: int,
         cues: Sequence[Tuple[int, int, int]], length: int, answer: int,
         question: str, early: str = 'end',
         jobs: Sequence[Tuple[int, int]] = (), asked: Optional[int] = None,
         **extra) -> framed.Puzzle:
    """A trial of *length* frames, the question on the last; *answer*
    is a place, *jobs* are ``(first frame, place)``."""
    if early not in EARLY:
        raise ValueError(early)
    data = {'look': look, 'cues': tuple(tuple(c) for c in cues),
            'early': early, 'jobs': tuple(tuple(j) for j in jobs),
            'asked': asked, 'layout': rng.choice(LAYOUTS),
            'hue': rng.randrange(len(framed.HUES_A)),
            'rim': rng.randrange(len(framed.RIMS)),
            'place': (rng.random(), rng.random())}
    data.update(extra)
    frames = tuple(range(length))
    choices = tuple(str(p + 1) for p in range(PLACES))
    return framed.puzzle(kind, k, frames, choices, port_of(look, answer),
                         data, question)


def job_port(puzzle: framed.Puzzle, job: int) -> int:
    return port_of(puzzle.data['look'], puzzle.data['jobs'][job][1])


class Run(framed.Run):
    """A trial's clock, with the wait closed to presses."""

    def __init__(self, puzzle: framed.Puzzle) -> None:
        super().__init__(puzzle)
        self.done = set()

    def job(self) -> Optional[int]:
        """The job showing now, or None."""
        f = self.t / FRAME + GIVE
        for j, (first, _place) in enumerate(self.puzzle.data['jobs']):
            if first <= f < first + JOB:
                return j
        return None

    def step(self, dt: float, control: Optional[int] = None) -> None:
        super().step(dt, control)
        if self.result is not None:
            return
        f = self.t / FRAME + GIVE
        for j, (first, _place) in enumerate(self.puzzle.data['jobs']):
            if first + JOB <= f and j not in self.done:
                self.result = (False, _('A job was left undone'))
                return

    def answer(self, k: int) -> None:
        if self.result is not None or not 0 <= k < PLACES:
            return
        if self.open:
            super().answer(k)
            return
        if self.puzzle.data['early'] == 'end':
            self.result = (False, _('Too soon: hands off until the '
                                    'question'))
            return
        j = self.job()
        if j is None or j in self.done or k != job_port(self.puzzle, j):
            self.result = (False, _('Not the job'))
            return
        self.done.add(j)


def act(run: Run, port: int) -> None:
    run.answer(port)
