# -*- coding: utf-8 -*-
"""Keep the Beat: tap along with a metronome, then keep it going alone.

A metronome ticks -- a click in the ears, a lamp, a swinging arm -- for
a bar or two; then a curtain drops over it and it falls silent, and the
beat has to be carried on: one tap for every beat that would have come,
each close enough to when it would have come. What is judged is only
the silent part.

Nothing on the screen moves with the beat once the curtain is down, so
the beat has to be held inside, as a person holds it. Each tap leaves a
mark on a strip below, and after the verdict the strip shows where the
beats really fell.

The ladder:

* rungs 1-3: a slow, steady beat, a wide window, six beats to carry;
* rungs 4-6: a narrower window, eight beats;
* rungs 7-9: any tempo from slow to brisk;
* rungs 10-12: a swing -- long, short, long, short;
* rungs 13-15: a rhythm of three: long, short, short;
* rungs 16-19: the metronome comes back for a bar halfway, then goes
  again -- and the window narrows;
* from rung 20: longer silences, tighter windows every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

TAP = 0
PORTS = 1
EVENTS = (TAP,)
LEAD = 0.8                    # seconds before the first tick


class Grade(NamedTuple):
    rung: int
    tempo: Tuple[float, float]   # seconds a beat, least and most
    pattern: Tuple[float, ...]   # beat lengths in a cycle, as shares
    window: float                # +- seconds a tap may be off
    heard: int                   # beats heard before the curtain
    silent: int                  # beats to carry alone
    reprise: bool                # the metronome comes back halfway
    need: float                  # share of beats that must be hit
    strays: int                  # taps allowed that hit no beat


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        tempo=((0.8, 0.8) if r < 7 else (0.45, 0.95)),
        pattern=((1.0,) if r < 10 else (1.35, 0.65) if r < 13
                 else (1.5, 0.75, 0.75) if r < 16 else
                 ((1.0,), (1.35, 0.65), (1.5, 0.75, 0.75))[r % 3]),
        window=(0.18 if r < 4 else 0.13 if r < 10 else 0.12 if r < 16
                else max(0.07, 0.1 - 0.004 * top)),
        heard=8 if r < 10 else 12,
        silent=(6 if r < 4 else 8 if r < 16 else 10 if r < 20
                else min(20, 12 + top)),
        reprise=r >= 16,
        need=0.75,
        strays=2)


class Song(NamedTuple):
    level: Grade
    beats: List[float]           # every beat's time, heard or not
    heard: List[bool]            # whether each beat is heard
    judged: List[int]            # the beats a tap must find
    end: float


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Song:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    unit = draw.uniform(*level.tempo)
    pat = level.pattern
    # Whole cycles, so the curtain falls on the cycle's first beat.
    def cycles(n):
        return max(1, -(-n // len(pat))) * len(pat)
    plan: List[bool] = [True] * cycles(level.heard)
    silent = cycles(level.silent)
    if level.reprise:
        half = cycles(silent // 2)
        plan += [False] * half + [True] * len(pat) * 2 + \
            [False] * max(len(pat), silent - half)
    else:
        plan += [False] * silent
    beats, t = [], LEAD
    for k in range(len(plan)):
        beats.append(round(t, 4))
        t += unit * pat[k % len(pat)]
    judged = [k for k, h in enumerate(plan) if not h]
    return Song(level, beats, plan, judged, beats[-1] + level.window + 0.8)


class Run:
    def __init__(self, song: Song) -> None:
        self.song = song
        self.level = song.level
        self.t = 0.0
        self.taps: List[float] = []
        self.result: Optional[Tuple[bool, str]] = None

    def curtain(self) -> bool:
        """Whether the metronome is hidden and silent now."""
        song = self.song
        for k, b in enumerate(song.beats):
            if b > self.t:
                # Between beats, the state of the beat to come.
                return not song.heard[k]
        return True

    def tap(self) -> None:
        if self.result is None:
            self.taps.append(self.t)

    def score(self) -> Tuple[int, int]:
        """Beats hit, and stray taps, in the silent part. Each tap goes
        to the nearest beat it can still claim."""
        song = self.song
        w = self.level.window
        free = set(song.judged)
        hits, strays = 0, 0
        for t in self.taps:
            near = [k for k in free if abs(song.beats[k] - t) <= w]
            if near:
                free.discard(min(near, key=lambda k: abs(song.beats[k] - t)))
                hits += 1
            elif any(not song.heard[k] and abs(song.beats[k] - t) < 3 * w
                     for k in range(len(song.beats))) or \
                    t > song.beats[song.judged[0]] - 3 * w:
                strays += 1
        return hits, strays

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.song.end:
            hits, strays = self.score()
            n = len(self.song.judged)
            need = int(round(self.level.need * n + 0.499))
            if hits >= need and strays <= self.level.strays:
                self.result = (True, _('%d of %d beats kept') % (hits, n))
            elif hits < need:
                self.result = (False, _('%d of %d beats kept -- %d needed')
                               % (hits, n, need))
            else:
                self.result = (False, _('%d taps off the beat') % strays)


def act(run: Run, port: int) -> None:
    if port == TAP:
        run.tap()


def autopilot(run: Run) -> List[int]:
    """Tap each beat of the silent part on the first step at or after it,
    whatever the step length."""
    w = run.level.window
    for k in run.song.judged:
        b = run.song.beats[k]
        if b <= run.t + 1e-9 and run.t - b < w and \
                not any(abs(t - b) <= w for t in run.taps):
            return [TAP]
    return []


def play(song: Song, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(song)
    while run.result is None:
        for port in pilot(run):
            act(run, port)
        run.step(dt)
    return run.result
