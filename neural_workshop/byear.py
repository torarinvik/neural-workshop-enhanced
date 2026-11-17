# -*- coding: utf-8 -*-
"""By Ear: hear a tune, then play it back.

A tune plays on a keyboard of one octave, and the keys do not light up
while it plays -- only the ear can follow it. Then play it back on the
same keys, note for note. A wrong key ends the try; so does waiting too
long.

* rung 1: two notes, on three keys far apart (C, E and G), slowly;
* rungs 2-3: three notes on the five keys of a pentatonic scale;
* rungs 4-6: four and five notes on the eight white keys;
* rungs 7-9: five and six notes on all thirteen keys;
* rungs 10-12: the tune is heard in one key and played back from
  another: the first key is lit, and the rest follow by the same steps;
* rungs 13 and up: some steps are two notes at once (press both), the
  tune grows a note every two rungs without end, and plays faster.

For the agent boundary: ports 0-12 press the keys from C to the C above;
the tune and every key pressed come on the audio channel.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import FrozenSet, List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

KEYS = 13
PORTS = KEYS
EVENTS = tuple(range(KEYS))
BASE = 261.63                  # middle C
LEAD = 0.8                     # silence before the tune
CHORD = 0.45                   # seconds to press the second key of a pair
PATCHES = ('flute', 'pluck', 'bell')
TUNE, PRESS, GOOD, BAD = range(4)

SCALES = {'three': (0, 4, 7), 'five': (0, 2, 4, 7, 9),
          'white': (0, 2, 4, 5, 7, 9, 11, 12), 'all': tuple(range(KEYS))}
WHITE = (0, 2, 4, 5, 7, 9, 11, 12)


def freq(key: int) -> float:
    return BASE * 2 ** (key / 12.0)


class Grade(NamedTuple):
    rung: int
    keys: Tuple[int, ...]      # the keys in play
    length: int                # steps in the tune
    note: float                # seconds a note
    shift: bool                # played back from another key
    pairs: float               # share of steps that are two notes at once
    patch: int                 # 0 flute, 1 pluck, 2 bell


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        keys, length, note = SCALES['three'], 2, 0.9
    elif r < 4:
        keys, length, note = SCALES['five'], 3, 0.75
    elif r < 7:
        keys, length, note = SCALES['white'], 4 + (r >= 5), 0.6
    elif r < 10:
        keys, length, note = SCALES['all'], 5 + (r >= 8), 0.5
    else:
        keys = SCALES['all']
        length = 6 + (r - 10) // 2
        note = max(0.16, 0.5 - 0.025 * (r - 10))
    return Grade(r, keys, length, note, r >= 10,
                 0.0 if r < 13 else min(0.5, 0.2 + 0.03 * (r - 13)),
                 0 if r < 7 else 1 if r < 16 else 2)


class Tune(NamedTuple):
    level: Grade
    heard: Tuple[FrozenSet[int], ...]      # what plays
    want: Tuple[FrozenSet[int], ...]       # what is to be played back
    lit: Optional[int]                     # the first key, when shifted


def _walk(level: Grade, draw: random.Random) -> List[FrozenSet[int]]:
    keys = level.keys
    out: List[FrozenSet[int]] = []
    at = draw.choice(keys)
    for _k in range(level.length):
        near = [k for k in keys if k != at and abs(k - at) <= 7] or \
            [k for k in keys if k != at]
        at = draw.choice(near) if out else at
        step = {at}
        if draw.random() < level.pairs:
            other = [k for k in keys if 3 <= abs(k - at) <= 9]
            if other:
                step.add(draw.choice(other))
        out.append(frozenset(step))
    return out


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Tune:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    want = _walk(level, draw)
    if not level.shift:
        return Tune(level, tuple(want), tuple(want), None)
    lo = min(min(s) for s in want)
    hi = max(max(s) for s in want)
    # heard somewhere else, but still on the keyboard's octave and a half
    choices = [d for d in range(-lo - 5, KEYS + 5 - hi) if d != 0]
    d = draw.choice(choices)
    heard = tuple(frozenset(k + d for k in s) for s in want)
    first = min(want[0])
    return Tune(level, heard, tuple(want), first)


class Run(object):
    def __init__(self, tune: Tune) -> None:
        self.tune = tune
        self.level = tune.level
        self.t = 0.0
        self.notes: List[Note] = []
        self.seed = 0
        self.done = 0                       # steps played back
        self.held: set = set()              # keys of the step under way
        self.first_at = 0.0
        self.pressed: List[Tuple[float, int, bool]] = []
        self.result: Optional[Tuple[bool, str]] = None
        lv = self.level
        t = LEAD
        for step in tune.heard:
            for k in step:
                self._note(t, lv.note * 0.92, freq(k), lv.patch, 0.45)
            t += lv.note
        self.listen_end = t + 0.3
        self.end = self.listen_end + 4.0 + 3.0 * len(tune.want)

    def _note(self, t, dur, f, voice, gain) -> None:
        self.seed += 1
        n = Note(t, dur, f, 0.0, 0.0, gain, gain, 0.8, voice, self.seed, -1,
                 0.0)
        k = len(self.notes)
        while k > 0 and self.notes[k - 1].t > t:
            k -= 1
        self.notes.insert(k, n)

    def listening(self) -> bool:
        return self.t < self.listen_end

    def press(self, key: int) -> None:
        if self.result is not None or self.listening() or \
                not 0 <= key < KEYS:
            return
        self._note(self.t, 0.35, freq(key), self.level.patch, 0.4)
        want = self.tune.want[self.done]
        right = key in want and key not in self.held
        self.pressed.append((self.t, key, right))
        if not right:
            self.result = (False, _('A wrong note: %d of %d played') % (
                self.done, len(self.tune.want)))
            self._note(self.t + 0.3, 0.4, 110.0, 2, 0.4)
            return
        if not self.held:
            self.first_at = self.t
        self.held.add(key)
        if self.held == set(want):
            self.held = set()
            self.done += 1
            if self.done == len(self.tune.want):
                self.result = (True, _('All %d played back') % self.done)
                self._note(self.t + 0.3, 0.3, 1320.0, 2, 0.3)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.held and self.t - self.first_at > CHORD:
            self.result = (False, _('Both notes of a pair, together'))
        elif self.t > self.end:
            self.result = (False, _('Too slow: %d of %d played') % (
                self.done, len(self.tune.want)))


def act(run: Run, port: int) -> None:
    run.press(port)


def autopilot(run: Run) -> List[int]:
    """Plays back what it heard, one key a call, a little after the
    tune ends."""
    if run.listening() or run.result is not None or \
            run.t < run.listen_end + 0.3:
        return []
    want = run.tune.want[run.done]
    left = sorted(set(want) - run.held)
    return left[:1]


def play(tune: Tune, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(tune)
    while run.result is None:
        for p in pilot(run):
            act(run, p)
        run.step(dt)
    return run.result
