# -*- coding: utf-8 -*-
"""Potter's Wheel: shape a spinning lump of clay to match a pot.

A cylinder of clay turns on a wheel. Press the pointer against it at
some height and the clay there moves, slowly, to where the pointer is:
in to narrow it, out to widen it. Match the outline of the pot you are
shown, from foot to rim, and take your hands off: when every band of
it is right and nothing is touching it, the pot is done.

Keys: Up and Down change the wheel's speed (a faster wheel shapes
faster and wobbles more); Space wets the clay, which dries as it turns
and will not move when dry.

The ladder:

* rungs 1-3: four bands, the pot drawn over the clay, clay that stays
  wet;
* rungs 4-6: six bands; the clay dries; moving one band drags its
  neighbours a little;
* rungs 7-9: eight bands; the pot is drawn beside the clay, not over
  it;
* rungs 10-12: the wheel wobbles at speed; a finer match is wanted;
* rungs 13-19: ten bands; the pot is shown for a few seconds and then
  taken away;
* from rung 20: more bands, a finer match, quicker drying and less time
  every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

FASTER, SLOWER, WET = H.KEYS, H.KEYS + 1, H.KEYS + 2
PORTS = H.KEYS + 3
EVENTS = tuple(range(PORTS))
AXIS, FOOT, TALL, UNIT = 500.0, 110.0, 330.0, 170.0   # the clay on screen
THIN, FAT = 0.16, 1.2          # past these it collapses
START = 0.6
HUM, SCRAPE, DONE, SQUEAK, SPLASH, BUZZ = range(6)
PATCHES = ('organ', 'wood', 'bell', 'chirp', 'glass', 'growl')


class Grade(NamedTuple):
    rung: int
    bands: int
    near: float                # how close each band has to be
    drag: float                # how much a band pulls its neighbours
    dry: float                 # seconds the clay stays wet, 0 for ever
    ghost: str                 # 'over', 'beside' or 'brief'
    wobble: float
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    bands = (4 if r < 4 else 6 if r < 7 else 8 if r < 13 else 10 if r < 20
             else min(16, 11 + top // 4))
    return Grade(
        rung=r, bands=bands,
        near=(0.09 if r < 4 else 0.075 if r < 10 else 0.06 if r < 20
              else max(0.035, 0.055 - 0.001 * top)),
        drag=0.0 if r < 4 else 0.15 if r < 13 else 0.22,
        dry=(0.0 if r < 4 else 9.0 if r < 13 else 6.0 if r < 20
             else max(3.0, 5.5 - 0.1 * top)),
        ghost='over' if r < 7 else 'beside' if r < 13 else 'brief',
        wobble=0.0 if r < 10 else 0.02 if r < 20 else min(0.05, 0.025
                                                         + 0.001 * top),
        seconds=bands * (9.0 if r < 7 else 7.5 if r < 13 else 6.5 if r < 20
                         else max(4.0, 6.0 - 0.06 * top)) + 6.0)


class Pot(NamedTuple):
    level: Grade
    shape: Tuple[float, ...]   # the radius wanted at each band, foot first
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Pot]:
    n = level.bands
    a, b = draw.uniform(0.12, 0.26), draw.uniform(-0.25, 0.25)
    phase, wave = draw.uniform(0, 6.28), draw.uniform(2.5, 5.5)
    shape = tuple(round(max(0.3, min(1.0, 0.6 + a * math.sin(
        phase + wave * k / n) + b * (k / (n - 1.0) - 0.5))), 3)
        for k in range(n))
    if max(abs(v - START) for v in shape) < 0.15:
        return None
    return Pot(level, shape, draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Pot:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


def band_y(n: int, k: float) -> float:
    """The screen height of the middle of band *k* of *n*."""
    return FOOT + TALL * (k + 0.5) / n


class Run(H.HandRun):
    def __init__(self, pot: Pot) -> None:
        super().__init__(pot.level.seconds)
        self.pot, self.level = pot, pot.level
        self.r: List[float] = [START] * pot.level.bands
        self.speed = 1                 # 1, 2 or 3
        self.wet = 1.0
        self.turn = 0.0                # the wheel's angle
        self.good_for = 0.0
        self.was_near = [False] * pot.level.bands
        self.hum_at = self.scrape_at = self.squeak_at = 0.0
        self.touching: Optional[int] = None

    def press(self) -> None:
        if self.result is None:
            self.hand.down = True

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if self.result is not None:
            return
        if port == FASTER:
            self.speed = min(3, self.speed + 1)
        elif port == SLOWER:
            self.speed = max(1, self.speed - 1)
        elif port == WET:
            self.wet = 1.0
            self.note(0.2, 700.0, SPLASH, 0.4)

    def band(self) -> Optional[int]:
        """The band the pointer is against, if it is near the clay."""
        n = self.level.bands
        k = int((self.hand.y - FOOT) / (TALL / n))
        if not 0 <= k < n or abs(self.hand.x - AXIS) > 1.5 * UNIT:
            return None
        return k

    def shown(self) -> bool:
        """Whether the pot wanted is still on show."""
        return self.level.ghost != 'brief' or self.t < 5.0

    def miss(self) -> float:
        return max(abs(a - b) for a, b in zip(self.r, self.pot.shape))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        level = self.level
        self.turn += dt * 3.0 * self.speed
        if level.dry:
            self.wet = max(0.0, self.wet - dt / level.dry)
        if self.t >= self.hum_at:
            self.hum_at = self.t + 0.3
            self.note(0.32, 55.0 * self.speed, HUM, 0.12)
        k = self.band() if self.hand.down else None
        self.touching = k
        if k is not None:
            if self.wet <= 0.0:
                if self.t >= self.squeak_at:
                    self.squeak_at = self.t + 0.35
                    self.note(0.15, 1500.0, SQUEAK, 0.35)
            else:
                want = abs(self.hand.x - AXIS) / UNIT + level.wobble * (
                    self.speed - 1) * math.sin(self.turn * 2.0)
                rate = 0.22 * self.speed * dt
                move = max(-rate, min(rate, want - self.r[k]))
                self.r[k] += move
                for j in (k - 1, k + 1):
                    if 0 <= j < level.bands:
                        self.r[j] += level.drag * move
                if abs(move) > 1e-5 and self.t >= self.scrape_at:
                    self.scrape_at = self.t + 0.12
                    self.note(0.1, 180.0 + 240.0 * self.r[k], SCRAPE, 0.25)
        for j, v in enumerate(self.r):
            if not THIN <= v <= FAT:
                self.note(0.5, 80.0, BUZZ, 0.6)
                self.result = (False, _('The pot collapsed'))
                return
            near = abs(v - self.pot.shape[j]) <= level.near
            if near and not self.was_near[j]:
                self.note(0.15, 660.0 * 2 ** (j / 12.0), DONE, 0.3)
            self.was_near[j] = near
        if all(self.was_near) and not self.hand.down:
            self.good_for += dt
            if self.good_for >= 0.8:
                self.result = (True, _('A fine pot'))
        else:
            self.good_for = 0.0
        if self.result is None and self.t >= self.end:
            self.result = (False, _('The clay went hard'))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Wet the clay, then press the worst band to where it should be:
    one port a step."""
    if run.result is not None:
        return []
    level, hand, pot = run.level, run.hand, run.pot
    if level.dry and run.wet < 0.3:
        return [WET]
    if run.speed < 2:
        return [FASTER]
    worst, gap = None, 0.55 * level.near
    for k, (a, b) in enumerate(zip(run.r, pot.shape)):
        if abs(a - b) > gap:
            worst, gap = k, abs(a - b)
    if hand.down and (worst is None or run.touching != worst or
                      abs(run.r[worst] - pot.shape[worst])
                      <= 0.3 * level.near):
        return [H.RELEASE]
    if worst is None:
        return []
    x = AXIS + UNIT * pot.shape[worst]
    y = band_y(level.bands, worst)
    if not hand.down:
        move = H.toward(hand, x, y, tol=3.0)
        return [move] if move is not None else [H.PRESS]
    return []


def play(pot: Pot, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(pot), pilot, EVENTS, act, dt)
