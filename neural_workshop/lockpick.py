# -*- coding: utf-8 -*-
"""Lock Pick: open a pin lock by feel and by ear.

A lock cut open, its pins hanging in a row. Two hands' work. One holds
tension on the plug: hold T and the tension builds, let go and it
eases; it has to stay in the band marked on its gauge -- too little
and pins that are set drop back, too much and the wrench slips, which
counts against you. The other works the pick: put its tip under a pin,
press, and raise it. Only one pin binds at a time. Raise that pin to
its own height, slowly, and it sets with a click; shove it past and the
lock jams and every pin drops.

The ladder:

* rungs 1-3: three pins that bind left to right; the binding pin glows
  and a tone climbs as it nears its height;
* rungs 4-6: four pins in any order; no glow -- the binding pin sounds
  stiff when the pick touches it;
* rungs 7-9: five pins; no climbing tone, only the click; a narrower
  band;
* rungs 10-12: pins that are not binding give false clicks, higher
  than the true one;
* rungs 13-19: six pins, and the lock's face is closed: the pins
  cannot be seen;
* from rung 20: more pins, finer heights, a narrower band and less
  time every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

TENSION = H.KEYS               # held
PORTS = H.KEYS + 1
EVENTS = H.HAND_EVENTS
LEFT, GAP, FLOOR, LIFT = 250.0, 70.0, 230.0, 170.0   # the pins on screen
UNDER = 20.0                   # how near under a pin the tip has to be
DWELL = 0.12                   # seconds at its height before a pin sets
CLICK, TICK, TONE, SLIP, JAM, OPEN = range(6)
PATCHES = ('wood', 'pluck', 'sine', 'growl', 'metal', 'bell')


class Grade(NamedTuple):
    rung: int
    pins: int
    fine: float                # how near its height a pin has to be
    band: Tuple[float, float]  # the tension wanted
    ordered: bool              # the pins bind left to right
    glow: bool
    tone: bool
    false: bool
    hidden: bool
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    pins = (3 if r < 4 else 4 if r < 7 else 5 if r < 13 else 6 if r < 20
            else min(10, 7 + top // 4))
    half = (0.25 if r < 7 else 0.2 if r < 20 else max(0.16, 0.2 - 0.002 * top))
    return Grade(
        rung=r, pins=pins,
        fine=(0.07 if r < 7 else 0.055 if r < 20
              else max(0.04, 0.055 - 0.0005 * top)),
        band=(0.55 - half, 0.55 + half),
        ordered=r < 4, glow=r < 4, tone=r < 7, false=r >= 10, hidden=r >= 13,
        seconds=pins * (9.0 if r < 7 else 7.5 if r < 20
                        else max(4.5, 7.0 - 0.06 * top)) + 6.0)


class Lock(NamedTuple):
    level: Grade
    heights: Tuple[float, ...]
    order: Tuple[int, ...]     # which pin binds first, second, ...
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Lock]:
    n = level.pins
    heights = tuple(round(draw.uniform(0.25, 0.85), 2) for _k in range(n))
    order = list(range(n))
    if not level.ordered:
        draw.shuffle(order)
    return Lock(level, heights, tuple(order), draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Lock:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


def pin_x(k: int) -> float:
    return LEFT + GAP * k


class Run(H.HandRun):
    def __init__(self, lock: Lock) -> None:
        super().__init__(lock.level.seconds)
        self.lock, self.level = lock, lock.level
        self.lift: List[float] = [0.0] * lock.level.pins
        self.set = 0                   # how many pins are set
        self.tension = 0.0
        self.slips = 0
        self.at_height = 0.0
        self.drop_at = 0.0
        self.under: Optional[int] = None
        self.tone_at = 0.0
        self.fooled: set = set()

    @property
    def binding(self) -> Optional[int]:
        order = self.lock.order
        return order[self.set] if self.set < len(order) else None

    def is_set(self, k: int) -> bool:
        return k in self.lock.order[:self.set]

    def in_band(self) -> bool:
        lo, hi = self.level.band
        return lo <= self.tension <= hi

    def over(self) -> Optional[int]:
        """The pin the pick's tip is under."""
        k = int(round((self.hand.x - LEFT) / GAP))
        if 0 <= k < self.level.pins and abs(self.hand.x - pin_x(k)) <= UNDER:
            return k
        return None

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        k = self.over()
        if k is not None and not self.is_set(k):
            stiff = k == self.binding
            self.note(0.05, 300.0 if stiff else 520.0, TICK, 0.4)

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        pass

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.controls(control)
        self.t += dt
        level, lock = self.level, self.lock
        self.tension = max(0.0, min(1.0, self.tension + dt * (
            0.9 if self.holding(TENSION) else -0.5)))
        if self.tension >= 0.97:
            self.tension = 0.5
            self.slips += 1
            self.note(0.3, 120.0, SLIP, 0.6)
            if self.slips >= 3:
                self.result = (False, _('The wrench slipped once too often'))
                return
        if self.tension < level.band[0] and self.set and \
                self.t >= self.drop_at:
            self.drop_at = self.t + 0.5
            self.set -= 1
            self.note(0.1, 200.0, CLICK, 0.35)
        k = self.over() if self.hand.down else None
        self.under = k
        for j in range(level.pins):
            if self.is_set(j):
                self.lift[j] = lock.heights[j]
            elif j == k:
                self.lift[j] = max(0.0, min(1.0, (self.hand.y - FLOOR)
                                            / LIFT))
            else:
                self.lift[j] = max(0.0, self.lift[j] - 4.0 * dt)
        b = self.binding
        if k is not None and k == b and self.in_band():
            off = self.lift[k] - lock.heights[k]
            if level.tone and self.t >= self.tone_at:
                self.tone_at = self.t + 0.1
                self.note(0.1, 300.0 + 500.0 * max(0.0, 1.0 - abs(off) * 3),
                          TONE, 0.3)
            if off > 2.2 * level.fine:
                self.set = 0
                self.at_height = 0.0
                self.note(0.4, 150.0, JAM, 0.6)
            elif abs(off) <= level.fine:
                self.at_height += dt
                if self.at_height >= DWELL:
                    self.at_height = 0.0
                    self.set += 1
                    self.note(0.08, 240.0, CLICK, 0.7)
                    if self.set >= level.pins:
                        self.note(0.5, 660.0, OPEN, 0.5)
                        self.result = (True, _('The lock turned'))
                        return
            else:
                self.at_height = 0.0
        elif k is not None and level.false and k != b and \
                not self.is_set(k):
            fake = 1.0 - lock.heights[k]
            if abs(self.lift[k] - fake) < 0.04:
                if k not in self.fooled:
                    self.fooled.add(k)
                    self.note(0.06, 420.0, CLICK, 0.5)
            else:
                self.fooled.discard(k)
        if self.t >= self.end:
            self.result = (False, _('Someone is coming'))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Keep the tension in the middle of its band and raise the binding
    pin gently to its height: one port a step."""
    if run.result is not None:
        return []
    hand, level = run.hand, run.level
    lo, hi = level.band
    if run.tension < (lo + hi) / 2 - 0.06 and not run.holding(TENSION):
        return [TENSION]
    b = run.binding
    x = pin_x(b)
    if hand.down and run.under != b:
        return [H.RELEASE]
    if not hand.down:
        move = H.toward(hand, x, FLOOR, tol=3.0)
        return [move] if move is not None else [H.PRESS]
    if not run.in_band():
        return []
    off = run.lock.heights[b] - run.lift[b]
    if off > 0.6 * level.fine:
        return [0 * 3 + (1 if off > 0.2 else 2)]      # up: medium or short
    return []


def play(lock: Lock, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(lock), pilot, EVENTS, act, dt)
