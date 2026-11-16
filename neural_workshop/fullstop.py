# -*- coding: utf-8 -*-
"""Full Stop: find where each sentence ends.

A few sentences of real text (Simple English Wikipedia, see
:mod:`neural_workshop.passages`) run together with every full stop and
every capital taken out:

    the rotation of venus is slow a venusian day is longer than a year

The task is to put the stops back. Click the last word of a sentence to
end the sentence there (and click it again to take the stop away); the
word after it takes a capital. Done (Enter) hands it in; it passes when
every stop is where it was written and there are no others. Reset (R)
takes all the stops away.

**What makes the stops the stops.** A run of words can often be cut in
more than one place. A passage is only dealt where every true break
joins two words that never stand side by side inside a sentence of the
54,000 the task reads: each break is a place English does not run on.

The ladder:

* rung 1: two sentences, and one more every two rungs, up to twelve;
* rungs 1-9: the number of sentences on the screen;
* rungs 14+: names lose their capitals too, so a capital is no clue;
* rungs 20+: short sentences, four to eight words, so there are more
  stops in the same number of words;
* the clock is a little under a second a word, and from rung 22 (when
  the sentences stop growing) it shortens without end.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import FrozenSet, List, NamedTuple, Optional, Set, Tuple

from . import hand as H
from . import passages as PS
from . import proofreader as PR
from .i18n import _

DONE_KEY = H.KEYS              # 14: hand it in
RESET = H.KEYS + 1             # 15: take every stop away
PORTS = H.KEYS + 2
EVENTS = tuple(range(PORTS))
TICK, UNTICK, DONE, MISS = range(4)
PATCHES = ('wood', 'wood', 'bell', 'growl')

MOST = 12                      # sentences at most
WORDS_MAX = 112                # words that fit on the page

# Where things are on the 1000 by 640 screen (y up).
TEXT_X = (60.0, 940.0)
TOP = 520.0
BOTTOM = 130.0
LINE = 62.0
CHAR, PAD, GAP, TILE_H = 10.5, 16.0, 10.0, 34.0
DONE_AT = PR.DONE_AT
RESET_AT = PR.RESET_AT
BUTTON_W, BUTTON_H = PR.BUTTON_W, PR.BUTTON_H


class Grade(NamedTuple):
    rung: int
    sentences: int
    hint: bool                 # the count of sentences shown
    flat: bool                 # names lose their capitals
    short: bool                # four to eight words a sentence
    pace: float                # seconds a word


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    n = min(MOST, 2 + (r - 1) // 2)
    pace = 0.9
    if r > 22:
        pace *= max(0.2, 1.0 - 0.025 * (r - 22))
    return Grade(r, n, r < 10, r >= 14, r >= 20, round(pace, 3))


class Machine(NamedTuple):
    level: Grade
    sentences: Tuple[Tuple[str, ...], ...]     # as written, lowercased
    words: Tuple[str, ...]                     # run together
    stops: FrozenSet[int]                      # a stop after these words
    seconds: float


def _sentences(level: Grade, draw: random.Random
               ) -> Optional[List[Tuple[str, ...]]]:
    lo, hi = (4, 8) if level.short else (5, 12)
    bank = PS.bank()
    out: List[Tuple[str, ...]] = []
    for _t in range(400):
        if len(out) >= level.sentences:
            break
        passage = PR._norm(draw.choice(bank))
        run = []
        for s in passage:
            if not lo <= len(s) <= hi:
                break
            run.append(s)
        out.extend(run[:level.sentences - len(out)])
    if len(out) < level.sentences:
        return None
    return out


def build(level: Grade, draw: random.Random) -> Optional[Machine]:
    sents = _sentences(level, draw)
    if sents is None:
        return None
    if level.flat:
        sents = [tuple(w.lower() for w in s) for s in sents]
    words: List[str] = []
    stops: Set[int] = set()
    for k, s in enumerate(sents):
        if k and PR.said(words[-1], s[0]):
            return None                        # it could run on there
        words.extend(s)
        stops.add(len(words) - 1)
    if len(words) > WORDS_MAX:
        return None
    stops.discard(len(words) - 1)              # the last stop is given
    seconds = round(20.0 + level.pace * len(words) + 4.0 * len(sents), 1)
    return Machine(level, tuple(sents), tuple(words), frozenset(stops),
                   seconds)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Machine:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=200)


# --- where things are ---------------------------------------------------

def layout(words) -> Tuple[List[Tuple[float, float, float]], float]:
    """Each word's tile (centre x, y, width) wrapped over the page, and
    the scale it is drawn at."""
    k = 1.0
    while True:
        out, x, y = [], TEXT_X[0], TOP
        for w in words:
            width = (len(w) * CHAR + PAD) * k
            if x + width > TEXT_X[1] and x > TEXT_X[0]:
                x, y = TEXT_X[0], y - LINE * k
            out.append((x + width / 2, y, width))
            x += width + GAP * k
        if y >= BOTTOM or k <= 0.5:
            return out, k
        k -= 0.05


# --- a run ----------------------------------------------------------------

class Run(H.HandRun):
    def __init__(self, machine: Machine) -> None:
        super().__init__(machine.seconds)
        self.machine, self.level = machine, machine.level
        self.stops: Set[int] = set()
        self.places, self.scale = layout(machine.words)

    def word_at(self, x: float, y: float) -> Optional[int]:
        for i, (cx, cy, w) in enumerate(self.places):
            if abs(x - cx) <= w / 2 + GAP * self.scale / 2 and \
                    abs(y - cy) <= TILE_H * self.scale / 2 + 4:
                return i
        return None

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        x, y = self.hand.x, self.hand.y
        if abs(y - DONE_AT[1]) <= BUTTON_H / 2:
            if abs(x - DONE_AT[0]) <= BUTTON_W / 2:
                return self.done()
            if abs(x - RESET_AT[0]) <= BUTTON_W / 2:
                return self.reset()
        i = self.word_at(x, y)
        if i is None or i == len(self.machine.words) - 1:
            return
        pan = (x - 500.0) / 500.0
        if i in self.stops:
            self.stops.discard(i)
            self.note(0.06, 330.0, UNTICK, 0.3, pan=pan)
        else:
            self.stops.add(i)
            self.note(0.06, 660.0, TICK, 0.3, pan=pan)

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if self.result is not None:
            return
        if port == DONE_KEY:
            self.done()
        elif port == RESET:
            self.reset()

    def reset(self) -> None:
        self.stops = set()
        self.note(0.1, 200.0, UNTICK, 0.3)

    def sentences_now(self) -> int:
        return len(self.stops) + 1

    def done(self) -> None:
        if self.result is not None:
            return
        if self.stops == set(self.machine.stops):
            self.note(0.6, 880.0, DONE, 0.5)
            self.result = (True, _('Every stop in its place'))
        else:
            self.note(0.5, 90.0, MISS, 0.5)
            miss = len(set(self.machine.stops) - self.stops)
            extra = len(self.stops - set(self.machine.stops))
            self.result = (False, _('%d stop(s) missing, %d too many') %
                           (miss, extra))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.end:
            self.result = (False, _('Out of time'))


act = H.act


# --- the reference player ---------------------------------------------------

def autopilot(run: Run) -> List[int]:
    """Knows where the stops go: clicks each word that is wrong, then
    hands it in."""
    if run.result is not None:
        return []
    for i in range(len(run.machine.words)):
        if (i in run.stops) != (i in run.machine.stops):
            x, y, _w = run.places[i]
            return _click(run, x, y)
    return _click(run, DONE_AT[0], DONE_AT[1])


def _click(run: Run, x: float, y: float) -> List[int]:
    if run.hand.down:
        return [H.RELEASE]
    move = H.toward(run.hand, x, y, tol=3.0)
    if move is not None:
        return [move]
    return [H.PRESS]


def play(machine: Machine, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(machine), pilot, EVENTS, act, dt)
