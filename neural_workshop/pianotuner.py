# -*- coding: utf-8 -*-
"""Piano Tuner: turn the pin until the string stops beating.

A reference note sounds, and with it a string that is out of tune. Two
notes nearly in tune *beat*: their sum swells and fades, faster the
further apart they are, and the beating slows and stops as they come
together. Turn the tuning pin until it stops, then say done. Nothing
on the screen shows the pitch: the pin's angle starts anywhere.

For an interval the string is tuned to the place where one of its
partials meets one of the reference's -- for a fifth, its second meets
the reference's third -- and the beating there is what is heard.

* rungs 1-3: one string, in unison with the reference, within 20, 12,
  then 8 cents (a cent is a hundredth of a semitone);
* rungs 4-6: an octave, then a fifth, within 10 to 6 cents;
* rungs 7-9: a fourth and a major third, within 6 to 5;
* rungs 10-12: two strings, the second tuned to the first, so a slip
  in the first is carried into the second;
* rungs 13 and up: the strings are stiff, as real piano strings are:
  their partials run sharp of whole multiples, so the beatless point is
  not where the arithmetic puts it; more strings, and the allowance
  shrinks every rung without end.

For the agent boundary: ports 0 and 1 turn the pin up and down
quickly, 2 and 3 slowly, for the step they are sent in; port 4 says
the string is in tune. Both notes are on the audio channel.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import livesound as LS
from .drshape import Note
from .i18n import _

UP, DOWN, UP_FINE, DOWN_FINE, DONE = range(5)
PORTS = 5
EVENTS = (DONE,)
COARSE, FINE = 60.0, 5.0       # cents a second
PATCHES = ('bell', 'wood')
INTERVALS = {'unison': (1, 1), 'octave': (2, 1), 'fifth': (3, 2),
             'fourth': (4, 3), 'third': (5, 4)}
NAMES = {'unison': _('in unison'), 'octave': _('an octave above'),
         'fifth': _('a fifth above'), 'fourth': _('a fourth above'),
         'third': _('a major third above')}
PARTIALS = (1.0, 0.55, 0.4, 0.28, 0.2, 0.14)


class Grade(NamedTuple):
    rung: int
    intervals: Tuple[str, ...]  # to choose from, a string at a time
    strings: int
    tol: float                  # cents
    stiff: float                # inharmonicity B
    seconds: float              # a string


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        return Grade(r, ('unison',), 1, (20.0, 12.0, 8.0)[r - 1], 0.0, 60)
    if r < 7:
        return Grade(r, ('octave',) if r == 4 else ('fifth',),
                     1, (10.0, 8.0, 6.0)[r - 4], 0.0, 60)
    if r < 10:
        return Grade(r, ('fourth',) if r == 7 else ('third',), 1,
                     (6.0, 6.0, 5.0)[r - 7], 0.0, 60)
    if r < 13:
        return Grade(r, ('unison', 'octave', 'fifth'), 2,
                     (5.0, 4.0, 4.0)[r - 10], 0.0, 60)
    return Grade(r, ('unison', 'octave', 'fifth', 'fourth', 'third'),
                 min(4, 2 + (r - 13) // 3), 4.0 * 0.92 ** (r - 12),
                 min(0.004, 0.0004 * (r - 12)), 60)


def stretch(n: int, b: float) -> float:
    """How far partial *n* of a stiff string runs sharp."""
    return math.sqrt(1 + b * n * n)


def target(ref: float, interval: str, b: float) -> float:
    """The string's fundamental at which it does not beat with *ref*:
    its partial *den* meets the reference's partial *num*."""
    num, den = INTERVALS[interval]
    return ref * num * stretch(num, b) / (den * stretch(den, b))


def cents(a: float, b: float) -> float:
    return 1200.0 * math.log(a / b, 2)


class Job(NamedTuple):
    level: Grade
    ref: float
    plan: Tuple[Tuple[str, float, float], ...]   # interval, start cents, pin


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Job:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    ref = draw.uniform(196.0, 262.0)
    plan = []
    for _k in range(level.strings):
        off = draw.uniform(max(40.0, 3 * level.tol), 150.0) * \
            draw.choice((-1, 1))
        plan.append((draw.choice(level.intervals), off, draw.uniform(0, 360)))
    return Job(level, ref, tuple(plan))


class Run(object):
    def __init__(self, job: Job) -> None:
        self.job = job
        self.level = job.level
        b = self.level.stiff
        self.t = 0.0
        self.k = 0                       # the string being tuned
        self.tuned: List[float] = []     # each string's final pitch
        self.since = 0.0
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        parts = [(n * stretch(n, b) / stretch(1, b), a)
                 for n, a in enumerate(PARTIALS, 1)]
        self.ref_track = LS.Track(parts)
        self.string_track = LS.Track(parts)
        self.tracks = [self.ref_track, self.string_track]
        self._start()
        self.end = self.level.seconds * self.level.strings + 2

    def anchor(self) -> float:
        """What the string now being tuned is tuned against."""
        return self.tuned[-1] if self.tuned else self.job.ref

    def goal(self) -> float:
        interval = self.job.plan[self.k][0]
        return target(self.anchor(), interval, self.level.stiff)

    def _start(self) -> None:
        _iv, off, _pin = self.job.plan[self.k]
        self.pitch = self.goal() * 2 ** (off / 1200.0)
        self.since = self.t
        self._sound()

    def error(self) -> float:
        """Cents the string is off, sharp positive."""
        return cents(self.pitch, self.goal())

    def pin(self) -> float:
        """The pin's angle on screen: turns with the pitch, from
        anywhere."""
        return (self.job.plan[self.k][2] + 3.0 * self.error()) % 360

    def _sound(self) -> None:
        b = self.level.stiff
        s1 = stretch(1, b)
        g = 0.0 if self.result is not None else 0.16
        self.ref_track.set(self.t, self.anchor() * s1, g, g)
        self.string_track.set(self.t, self.pitch * s1, g, g)

    def _note(self, f, voice, gain=0.3) -> None:
        self.notes.append(Note(self.t, 0.3, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        on = {control} if isinstance(control, int) else set(control or ())
        rate = (COARSE * ((UP in on) - (DOWN in on)) +
                FINE * ((UP_FINE in on) - (DOWN_FINE in on)))
        self.pitch *= 2 ** (rate * dt / 1200.0)
        if self.t - self.since > self.level.seconds:
            self.result = (False, _('Out of time: %+.0f cents') % self.error())
            self._note(110.0, 1)
        self._sound()

    def done(self) -> None:
        if self.result is not None:
            return
        e = self.error()
        if abs(e) > self.level.tol:
            self.result = (False, _('%.0f cents %s') % (
                abs(e), _('sharp') if e > 0 else _('flat')))
            self._note(110.0, 1)
            self._sound()
            return
        self.tuned.append(self.pitch)
        self._note(1320.0, 0, 0.2)
        if len(self.tuned) == self.level.strings:
            self.result = (True, _('In tune: %+.1f cents') % e)
            self._sound()
            return
        self.k += 1
        self._start()


def act(run: Run, port: int) -> None:
    if port == DONE:
        run.done()


def autopilot(run: Run) -> List[int]:
    if run.result is not None:
        return []
    e = run.error()
    if abs(e) > 12:
        return [DOWN if e > 0 else UP]
    if abs(e) > run.level.tol * 0.3:
        return [DOWN_FINE if e > 0 else UP_FINE]
    return [DONE]


def mix(run: Run, t0: float, t1: float) -> bytes:
    return LS.mix(run.tracks, t0, t1, run.notes, LS.make_patches(PATCHES))


def play(job: Job, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(job)
    while run.result is None:
        ports = pilot(run)
        held = [p for p in ports if p not in EVENTS]
        for p in ports:
            if p in EVENTS:
                act(run, p)
        run.step(dt, held[0] if held else None)
    return run.result
