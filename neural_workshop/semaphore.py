# -*- coding: utf-8 -*-
"""Semaphore: read the flags, answer with your own, and say the letter.

A signaller on a far ship holds two flags. Each pair of positions is a
letter in the workshop's own code. Drag your own two flags to the same
pose to show you have it, then type the letter, before the signaller
moves on. A wrong letter, flags that do not match, or a signal you let
pass is a strike.

The ladder:

* rungs 1-3: four slow letters of a word, each letter written beside
  the signaller: learn the code;
* rungs 4-6: the letter is no longer written; the code chart is on the
  screen;
* rungs 7-9: the ship rolls, so nothing is quite upright;
* rungs 10-12: the chart shows only at the start of each signal; two
  strikes lose;
* rungs 13-15: the signaller sometimes turns their back: what you see
  is then the mirror of the letter, and yours must be the letter;
* rungs 16-19: no chart, and letters that spell nothing;
* from rung 20: fog, and a faster hand every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
PORTS = H.KEYS + 26                     # a key for every letter
EVENTS = tuple(range(PORTS))
PIVOT = (500.0, 150.0)                  # your shoulders
ARM = 115.0
FAR = (500.0, 455.0)                    # the signaller's
FAR_ARM = 62.0
GRAB = 34.0
BELL, RIGHT, WRONG, CLICK, SEA = range(5)
PATCHES = ('bell', 'chirp', 'growl', 'wood', 'hiss')
WORDS = {
    4: ('SHIP', 'MAST', 'KNOT', 'WIND', 'PORT', 'DECK', 'TIDE', 'HELM',
        'CREW', 'FLAG', 'BUOY', 'JUMP', 'QUAY', 'WAVE', 'ZINC', 'FOXY'),
    5: ('STORM', 'CABIN', 'WHARF', 'PILOT', 'NORTH', 'QUICK', 'JETTY',
        'EXTRA', 'ZEBRA', 'GLOVE'),
    6: ('ANCHOR', 'VOYAGE', 'HARBOR', 'SIGNAL', 'RUDDER', 'KEELED',
        'JIGSAW', 'OXYGEN'),
    7: ('CAPTAIN', 'COMPASS', 'LANTERN', 'WHISTLE', 'JOURNEY', 'QUARTER'),
    8: ('STARLING', 'MIDNIGHT', 'FLAGSHIP', 'OVERBOARD'[:8], 'WINDWARD'),
}


def _code() -> Dict[str, Tuple[int, int]]:
    pairs = [(a, b) for a in range(8) for b in range(a + 1, 8)]
    random.Random(1851).shuffle(pairs)
    return dict(zip(LETTERS, pairs))


CODE = _code()                          # letter -> two of eight positions


def way(angle: float) -> Tuple[float, float]:
    """Degrees round from straight down, clockwise as you look."""
    a = math.radians(angle)
    return (-math.sin(a), -math.cos(a))


class Grade(NamedTuple):
    rung: int
    letters: int
    hold: float                # seconds a signal stays up
    near: float                # degrees a flag may be off
    help: str                  # 'named', 'chart', 'peek' or 'none'
    roll: float                # degrees the ship rolls
    turns: bool
    words: bool
    fog: bool
    strikes: int
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    letters = 4 if r < 7 else 5 if r < 10 else 6 if r < 16 else \
        min(14, 7 + top // 5)
    hold = (10.0 if r < 4 else 9.0 if r < 7 else 8.0 if r < 10
            else 7.0 if r < 13 else 6.5 if r < 16 else 5.5 if r < 20
            else max(2.0, 5.0 - 0.07 * top))
    return Grade(
        rung=r, letters=letters, hold=hold,
        near=18.0 if r < 10 else 14.0 if r < 20 else 11.0,
        help=('named' if r < 4 else 'chart' if r < 10 else 'peek'
              if r < 16 else 'none'),
        roll=0.0 if r < 7 else 10.0 if r < 20 else min(22.0, 12.0
                                                       + 0.3 * top),
        turns=r >= 13, words=r < 16, fog=r >= 20,
        strikes=3 if r < 10 else 2,
        seconds=2.0 + letters * (hold + 0.8) + 0.5)


class Message(NamedTuple):
    level: Grade
    text: str
    turned: Tuple[bool, ...]   # is their back to you for this letter?
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Message]:
    if level.words and level.letters in WORDS:
        text = draw.choice(WORDS[level.letters])
    else:
        text = ''.join(draw.choice(LETTERS) for _i in range(level.letters))
    turned = tuple(level.turns and draw.random() < 0.45 for _c in text)
    return Message(level, text, turned, draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Message:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


def flip(pose) -> Tuple[int, ...]:
    return tuple(sorted((8 - k) % 8 for k in pose))


class Run(H.HandRun):
    def __init__(self, message: Message) -> None:
        super().__init__(message.level.seconds)
        self.message, self.level = message, message.level
        self.flags = [20.0, 340.0]     # degrees, yours
        self.held: Optional[int] = None
        self.read = [None] * len(message.text)   # True, False or None
        self.strikes = 0
        self.said = ''                 # the last thing that went wrong
        self.rung_at = -1
        self.matched = False
        self.hand.to(500.0, 300.0)

    # --- the clock
    def span(self) -> float:
        return self.level.hold + 0.8

    def index(self) -> Optional[int]:
        """Which signal is up now, if one is."""
        t = self.t - 2.0
        if t < 0:
            return None
        k = int(t // self.span())
        if k >= len(self.message.text) or t - k * self.span() \
                >= self.level.hold:
            return None
        return k

    def since(self) -> float:
        return (self.t - 2.0) % self.span()

    # --- the picture
    def roll(self) -> float:
        return self.level.roll * math.sin(self.t * 0.9)

    def fogged(self) -> bool:
        return self.level.fog and math.sin(self.t * 1.3) > 0.45

    def theirs(self) -> Tuple[float, float]:
        """Their two flags as you see them, in degrees, roll and all."""
        k = self.index()
        if k is None:
            return (8.0 + self.roll(), 352.0 + self.roll())
        pose = CODE[self.message.text[k]]
        if self.message.turned[k]:
            pose = flip(pose)
        return tuple(p * 45.0 + self.roll() for p in pose)

    def back(self) -> bool:
        k = self.index()
        return k is not None and self.message.turned[k]

    def helped(self) -> str:
        if self.level.help == 'peek':
            return 'chart' if self.index() is not None and \
                self.since() < 0.3 * self.level.hold else 'none'
        return self.level.help

    def tip(self, which: int) -> Tuple[float, float]:
        d = way(self.flags[which])
        return (PIVOT[0] + ARM * d[0], PIVOT[1] + ARM * d[1])

    def pose(self) -> Optional[Tuple[int, ...]]:
        """Your flags as positions, if both are on one."""
        out = []
        for a in self.flags:
            k = int(round(a / 45.0)) % 8
            off = abs((a - k * 45.0 + 180.0) % 360.0 - 180.0)
            if off > self.level.near:
                return None
            out.append(k)
        return tuple(sorted(out))

    # --- the hands
    def press(self) -> None:
        self.hand.down = True
        best = None
        for k in (0, 1):
            x, y = self.tip(k)
            d = math.hypot(self.hand.x - x, self.hand.y - y)
            if d <= GRAB and (best is None or d < best[0]):
                best = (d, k)
        self.held = best[1] if best else None

    def release(self) -> None:
        self.hand.down = False
        self.held = None

    def key(self, port: int) -> None:
        letter = LETTERS[port - H.KEYS]
        k = self.index()
        if k is None or self.read[k] is not None:
            return
        if self.pose() != CODE[self.message.text[k]]:
            return self._strike(k, _('Your flags do not match'))
        if letter != self.message.text[k]:
            return self._strike(k, _('That was %s') % self.message.text[k])
        self.read[k] = True
        self.note(0.2, 990.0, RIGHT, 0.5)

    def _strike(self, k: int, why: str) -> None:
        self.read[k] = False
        self.strikes += 1
        self.said = why
        self.note(0.3, 120.0, WRONG, 0.5)
        if self.strikes >= self.level.strikes:
            self.result = (False, why)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        before = self.index()
        self.t += dt
        if self.held is not None and self.hand.down:
            dx, dy = self.hand.x - PIVOT[0], self.hand.y - PIVOT[1]
            if math.hypot(dx, dy) > 12.0:
                self.flags[self.held] = math.degrees(
                    math.atan2(-dx, -dy)) % 360.0
        now = self.index()
        if now is not None and now != self.rung_at:
            self.rung_at = now
            self.note(0.5, 660.0, BELL, 0.5)
        if before is not None and now != before \
                and self.read[before] is None:
            self._strike(before, _('You let %s pass')
                         % self.message.text[before])
            if self.result is not None:
                return
        match = now is not None and \
            self.pose() == CODE[self.message.text[now]]
        if match and not self.matched and self.level.rung < 7:
            self.note(0.05, 520.0, CLICK, 0.35)
        self.matched = match
        if self.t >= self.end:
            done = sum(1 for r in self.read if r)
            self.result = (True, _('%d of %d read') % (done,
                                                       len(self.read)))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Put each flag on the letter's pose, then type it."""
    k = run.index()
    if run.result is not None or k is None or run.read[k] is not None:
        return [H.RELEASE] if run.hand.down else []
    want = [p * 45.0 for p in CODE[run.message.text[k]]]

    def off(a, b):
        return abs((a - b + 180.0) % 360.0 - 180.0)
    straight = off(run.flags[0], want[0]) + off(run.flags[1], want[1])
    crossed = off(run.flags[0], want[1]) + off(run.flags[1], want[0])
    if crossed < straight:
        want.reverse()
    fine = 0.4 * run.level.near
    for which in (0, 1):
        if off(run.flags[which], want[which]) <= fine:
            continue
        if run.held != which:
            if run.hand.down:
                return [H.RELEASE]
            x, y = run.tip(which)
            move = H.toward(run.hand, x, y, tol=6.0)
            return [move] if move is not None else [H.PRESS]
        d = way(want[which])
        move = H.toward(run.hand, PIVOT[0] + ARM * d[0],
                        PIVOT[1] + ARM * d[1], tol=4.0)
        return [move] if move is not None else [H.RELEASE]
    if run.hand.down:
        return [H.RELEASE]
    return [H.KEYS + LETTERS.index(run.message.text[k])]


def play(message: Message, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(message), pilot, EVENTS, act, dt)
