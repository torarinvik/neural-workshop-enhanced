# -*- coding: utf-8 -*-
"""Night Watch: a dark warehouse, one torch, and somebody at the safe.

The warehouse is dark; you see only what your torch (the pointer)
lights. People come in at the doors: thieves, who walk to the safe;
the guard on his round; and the cat. The night's orders say how to
tell a thief. Click a thief to catch them; click anyone else and it is
a strike, and a click on nobody wastes one of your few whistle blasts.
A thief at the safe ends the night. The floor may be wider
than you can see: Left / A and Right / D turn you along it, and every
footstep sounds from where it falls.

The ladder:

* rungs 1-3: two slow thieves in red caps, a floor you see whole, a
  wide torch; thieves' steps are low, the guard's keys jingle;
* rungs 4-6: a guard and a cat about; three thieves;
* rungs 7-9: a floor wider than the view;
* rungs 10-12: the orders name tonight's colours, which change;
  a narrower torch; two strikes lose;
* rungs 13-15: every step sounds the same;
* rungs 16-19: a wider floor yet, and thieves who do not walk straight;
* from rung 20: more thieves, quicker, in a smaller light every rung;
  one strike loses.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

LEFT, RIGHT = H.KEYS, H.KEYS + 1          # held: turn along the floor
PORTS = H.KEYS + 2
EVENTS = H.HAND_EVENTS
SAFE = (0.0, 3.0)
DEEP = 6.0                                # the floor runs z 0..6
PAN = 5.0
SEEN = 4.6                                # half the floor in view
STEP, KEYS_, MEOW, CAUGHT, WRONG, ALARM = range(6)
PATCHES = ('wood', 'metal', 'chirp', 'bell', 'growl', 'brass')
COLOURS = ('red', 'green', 'blue', 'yellow', 'white')
THIEF, GUARD, CAT = 'thief', 'guard', 'cat'


class Grade(NamedTuple):
    rung: int
    thieves: int
    others: int
    half: float                # half the floor's width
    cross: float               # seconds a thief takes to the safe
    beam: float                # the torch's radius on the screen
    fixed: bool                # thieves always in red
    telling: bool              # steps tell who walks
    weave: float               # how far a thief strays from the line
    strikes: int
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    thieves = 2 if r < 4 else 3 if r < 10 else 4 if r < 20 else \
        min(12, 5 + top // 6)
    cross = (16.0 if r < 4 else 14.0 if r < 10 else 12.0 if r < 20
             else max(6.0, 11.0 - 0.08 * top))
    gap = 0.55 * cross
    return Grade(
        rung=r, thieves=thieves,
        others=0 if r < 4 else 2 if r < 10 else 3 if r < 20
        else min(8, 4 + top // 8),
        half=4.4 if r < 7 else 8.0 if r < 16 else 12.0,
        cross=cross,
        beam=(150.0 if r < 10 else 115.0 if r < 20
              else max(60.0, 105.0 - 0.8 * top)),
        fixed=r < 10, telling=r < 13,
        weave=0.0 if r < 16 else 1.2,
        strikes=3 if r < 10 else 2 if r < 20 else 1,
        seconds=2.0 + thieves * gap + cross + 2.0)


class Walker(NamedTuple):
    kind: str
    colour: str
    enters: float
    start: Tuple[float, float]
    goal: Tuple[float, float]
    speed: float
    phase: float


class Night(NamedTuple):
    level: Grade
    thief: str                 # the colour thieves wear tonight
    guard: str
    walkers: Tuple[Walker, ...]
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Night]:
    if level.fixed:
        thief, guard = 'red', 'blue'
    else:
        thief, guard = draw.sample(COLOURS, 2)
    walkers = []
    gap = 0.55 * level.cross
    for k in range(level.thieves):
        side = draw.choice((-1.0, 1.0))
        start = (side * level.half, draw.uniform(0.8, DEEP - 0.8))
        far = math.hypot(start[0] - SAFE[0], start[1] - SAFE[1])
        walkers.append(Walker(THIEF, thief, 2.0 + k * gap
                              + draw.uniform(0.0, 0.3 * gap), start, SAFE,
                              far / level.cross, draw.uniform(0, 6.28)))
    for k in range(level.others):
        kind = GUARD if k % 2 == 0 else CAT
        side = draw.choice((-1.0, 1.0))
        z = draw.uniform(0.8, DEEP - 0.8)
        walkers.append(Walker(
            kind, guard if kind == GUARD else 'grey',
            draw.uniform(0.0, level.seconds * 0.7), (side * level.half, z),
            (-side * level.half, draw.uniform(0.8, DEEP - 0.8)),
            (2.0 * level.half / level.cross) * (1.0 if kind == GUARD
                                                else 1.7),
            draw.uniform(0, 6.28)))
    return Night(level, thief, guard, tuple(walkers),
                 draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Night:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


class Run(H.HandRun):
    def __init__(self, night: Night) -> None:
        super().__init__(night.level.seconds)
        self.night, self.level = night, night.level
        self.cam = 0.0
        self.gone = [False] * len(night.walkers)    # caught, or left
        self.caught = 0
        self.strikes = 0
        self.blasts = night.level.thieves + 3      # clicks you have
        self.step_at = [w.enters for w in night.walkers]

    # --- where things are
    def room(self) -> float:
        """How far the view can turn either way."""
        if self.level.half <= SEEN:
            return 0.0
        return self.level.half - SEEN + 0.6

    def view(self):
        return H.lens((self.cam, 2.3, 11.5), (self.cam, 0.9, 3.0), 760.0,
                      500.0, 300.0)

    def where(self, k: int) -> Optional[Tuple[float, float]]:
        """Walker *k* on the floor now, if they are in the building."""
        w = self.night.walkers[k]
        if self.gone[k] or self.t < w.enters:
            return None
        dx, dz = w.goal[0] - w.start[0], w.goal[1] - w.start[1]
        far = math.hypot(dx, dz)
        went = min(far, (self.t - w.enters) * w.speed)
        f = went / far
        x, z = w.start[0] + dx * f, w.start[1] + dz * f
        if w.kind == THIEF and self.level.weave:
            bend = self.level.weave * math.sin(math.pi * f) \
                * math.sin(w.phase + 1.3 * (self.t - w.enters))
            x, z = x - dz / far * bend, z + dx / far * bend
            z = max(0.4, min(DEEP - 0.4, z))
        return (x, z)

    def arrived(self, k: int) -> bool:
        w = self.night.walkers[k]
        far = math.hypot(w.goal[0] - w.start[0], w.goal[1] - w.start[1])
        return (self.t - w.enters) * w.speed >= far

    def height(self, k: int) -> float:
        return 0.3 if self.night.walkers[k].kind == CAT else 1.0

    def spot(self, k: int):
        """Where walker *k*'s middle is on the screen, and how big a
        unit of them is there."""
        at = self.where(k)
        if at is None:
            return None
        q = self.view().see((at[0], self.height(k), at[1]))
        if q is None:
            return None
        return (q[0], q[1], 760.0 / q[2])

    def lit(self, k: int) -> bool:
        q = self.spot(k)
        return q is not None and math.hypot(q[0] - self.hand.x,
                                            q[1] - self.hand.y) \
            <= self.level.beam + 0.3 * q[2]

    def under(self) -> Optional[int]:
        best = None
        for k in range(len(self.night.walkers)):
            q = self.spot(k)
            if q is None:
                continue
            wide = (0.45 if self.night.walkers[k].kind != CAT else 0.4) \
                * q[2]
            tall = self.height(k) * q[2]
            if abs(self.hand.x - q[0]) <= wide + 4 and \
                    abs(self.hand.y - q[1]) <= tall + 4:
                d = math.hypot(self.hand.x - q[0], self.hand.y - q[1])
                if best is None or d < best[0]:
                    best = (d, k)
        return None if best is None else best[1]

    def orders(self) -> str:
        return _('Tonight the thieves wear %s. The guard wears %s.') % (
            _(self.night.thief), _(self.night.guard))

    # --- the hands
    def press(self) -> None:
        self.hand.down = True
        k = self.under()
        self.blasts -= 1
        if k is None:
            self.note(0.15, 1200.0, KEYS_, 0.3)
            if self.blasts <= 0:
                self.result = (False, _('No whistle left'))
            return
        w = self.night.walkers[k]
        if w.kind == THIEF:
            self.gone[k] = True
            self.caught += 1
            self.note(0.3, 880.0, CAUGHT, 0.55, pan=self._pan(k))
            if self.caught >= self.level.thieves:
                self.result = (True, _('Every thief caught'))
        else:
            self.strikes += 1
            self.note(0.3, 130.0, WRONG, 0.5)
            if self.strikes >= self.level.strikes:
                self.result = (False, _('That was the %s') % _(w.kind))
            elif self.blasts <= 0:
                self.result = (False, _('No whistle left'))

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        pass

    def _pan(self, k: int) -> float:
        at = self.where(k)
        return 0.0 if at is None else max(-1.0, min(1.0, (at[0] - self.cam)
                                                    / SEEN))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.controls(control)
        self.t += dt
        turn = (self.holding(RIGHT) - self.holding(LEFT)) * PAN * dt
        self.cam = max(-self.room(), min(self.room(), self.cam + turn))
        for k, w in enumerate(self.night.walkers):
            if self.gone[k] or self.t < w.enters:
                continue
            if self.arrived(k):
                if w.kind == THIEF:
                    self.note(0.6, 196.0, ALARM, 0.6)
                    self.result = (False, _('The safe is robbed'))
                    return
                self.gone[k] = True
                continue
            if self.t >= self.step_at[k]:
                quick = w.kind == CAT
                self.step_at[k] = self.t + (0.9 if quick else 0.48)
                away = abs(self.where(k)[0] - self.cam)
                gain = 0.42 / (1.0 + 0.12 * away)
                if quick:
                    self.note(0.18, 700.0, MEOW, gain, pan=self._pan(k))
                elif w.kind == GUARD and self.level.telling:
                    self.note(0.07, 1500.0, KEYS_, gain, pan=self._pan(k))
                else:
                    self.note(0.06, 150.0 if self.level.telling
                              or w.kind == THIEF else 150.0, STEP, gain,
                              pan=self._pan(k))
        if self.t >= self.end:
            self.result = (False, _('Dawn: %d of %d caught')
                           % (self.caught, self.level.thieves))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Go to the thief nearest the safe: turn until they are in view,
    put the torch on them, click."""
    if run.result is not None:
        return []
    if run.hand.down:
        return [H.RELEASE]
    best = None
    for k, w in enumerate(run.night.walkers):
        at = run.where(k)
        if w.kind != THIEF or at is None:
            continue
        d = math.hypot(at[0] - SAFE[0], at[1] - SAFE[1])
        if best is None or d < best[0]:
            best = (d, k, at)
    if best is None:
        return []
    _d, k, at = best
    lean = at[0] - run.cam
    if abs(lean) > 3.2 and abs(run.cam + math.copysign(0.5, lean)) \
            <= run.room():
        port = RIGHT if lean > 0 else LEFT
        if not run.holding(port):
            return [port]
    q = run.spot(k)
    if q is None:
        return []
    if run.under() == k:
        return [H.PRESS]
    move = H.toward(run.hand, q[0], q[1], tol=6.0)
    return [move] if move is not None else []


def play(night: Night, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(night), pilot, EVENTS, act, dt)
