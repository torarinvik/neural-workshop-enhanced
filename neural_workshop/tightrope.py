# -*- coding: utf-8 -*-
"""Tightrope: walk the wire with a balance pole.

You are on a wire strung between two towers, high over a city, looking
along it at the far platform, holding a long pole. Move the mouse left
and right and the pole slides that way through your hands -- not at
once, it is heavy and follows the hand a moment behind -- which tips
you back the other way: when you lean left, put the pole out to the right. Up (or
W) takes a step, and each step jolts you a little to one side and then
the other. Lean too far and you are off.

Wind gusts are heard coming -- from the side they will blow from --
before they hit. From rung 10 birds land on the pole and weigh that end
down until you click them off, which means reaching out to them.

The ladder:

* rungs 1-3: six steps, gentle jolts, plenty of time;
* rungs 4-6: ten steps; the wire sways under you;
* rungs 7-9: gusts of wind;
* rungs 10-12: birds on the pole;
* rungs 13-15: fourteen steps, a livelier wire, stronger gusts, and a
  breeze that never quite stops and keeps changing its mind;
* rungs 16-19: the wire is springy and swings sideways under you: your
  steps set it going, leaning shoves it the other way, and its swing
  throws you about in turn;
* from rung 20: the wire bounces too, and a high bounce makes every lean
  grow faster; more steps, harder jolts, more wind, swing, bounce and
  birds and less time every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

STEP = H.KEYS
PORTS = H.KEYS + 1
EVENTS = tuple(range(PORTS))
REACH = 480.0                  # screen units for the pole right out
LAG = 0.18                     # seconds the pole takes to follow the hand
STIFF = 9.0                    # the wire's sideways spring
BOING = 30.0                   # its up-and-down spring
PULL = 5.0                     # how hard the pole rights you
FALL = 0.7                     # radians of lean that is a fall
PERCH = 0.6                    # how far along the pole a bird sits
TICK, WIND, BIRD, DONE, CREAK, FELL = range(6)
PATCHES = ('wood', 'pad', 'chirp', 'bell', 'brass', 'growl')


class Grade(NamedTuple):
    rung: int
    steps: int
    jolt: float
    tip: float                 # how fast a lean grows
    sway: float
    gusts: int
    blow: float
    birds: int
    breeze: float              # a steady wind that wanders
    spring: float              # how much the wire swings sideways
    bounce: float              # how much a step makes it bounce
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    steps = (6 if r < 4 else 10 if r < 13 else 14 if r < 20
             else 16 + top // 2)
    return Grade(
        rung=r, steps=steps,
        jolt=(0.25 if r < 4 else 0.4 if r < 13 else 0.55 if r < 20
              else min(0.7, 0.6 + 0.005 * top)),
        tip=2.5 if r < 13 else 3.5 if r < 20 else min(4.6, 3.6 + 0.04 * top),
        sway=0.0 if r < 4 else 0.25 if r < 13 else 0.45,
        gusts=0 if r < 7 else 2 if r < 13 else 3 if r < 20 else 4 + top // 5,
        blow=0.9 if r < 13 else 1.4 if r < 20 else min(1.7, 1.5 + 0.01 * top),
        birds=0 if r < 10 else 1 if r < 13 else 2 if r < 20
        else 3 + top // 4,
        breeze=0.0 if r < 13 else 0.5 if r < 20 else min(1.0, 0.6 + 0.02 * top),
        spring=0.0 if r < 16 else 0.8 if r < 20 else min(1.3, 1.0 + 0.015 * top),
        bounce=0.0 if r < 20 else min(1.1, 0.8 + 0.015 * top),
        seconds=steps * (3.0 if r < 4 else 2.4 if r < 13 else 2.0 if r < 20
                         else max(1.1, 1.9 - 0.03 * top)) + 5.0)


class Gust(NamedTuple):
    t: float
    dur: float
    push: float                # signed


class Walk(NamedTuple):
    level: Grade
    gusts: Tuple[Gust, ...]
    birds: Tuple[Tuple[float, int], ...]   # when, and which end (-1, 1)
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Walk]:
    span = level.seconds - 6.0
    gusts = tuple(sorted(Gust(draw.uniform(2.5, span), draw.uniform(0.8,
                                                                    1.6),
                              level.blow * draw.choice((-1, 1)))
                         for _k in range(level.gusts)))
    birds = tuple(sorted((draw.uniform(2.0, span), draw.choice((-1, 1)))
                         for _k in range(level.birds)))
    return Walk(level, gusts, birds, draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Walk:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


class Run(H.HandRun):
    def __init__(self, walk: Walk) -> None:
        super().__init__(walk.level.seconds)
        self.walk, self.level = walk, walk.level
        self.lean = 0.0                # radians, positive to the right
        self.rate = 0.0
        self.taken = 0
        self.foot = 1
        self.rest = 0.0                # until the next step may be taken
        self.perched: List[int] = []   # the ends birds are sitting on
        self.bird_no = 0
        self.warned = [False] * len(walk.gusts)
        self.creak_at = 0.0
        self.held = 0.0                # where the pole is, -1 to 1
        self.swing = self.swing_v = 0.0   # the wire sideways
        self.boing = self.boing_v = 0.0   # the wire up and down
        draw = random.Random(walk.seed)
        self.phase = (draw.uniform(0, 6.3), draw.uniform(0, 6.3))

    def aim(self) -> float:
        """Where the hand wants the pole, -1 left to 1 right."""
        return max(-1.0, min(1.0, (self.hand.x - H.W / 2) / REACH))

    def pole(self) -> float:
        """How far out the pole is, -1 left to 1 right."""
        return self.held

    def gust(self) -> float:
        for g in self.walk.gusts:
            if g.t <= self.t < g.t + g.dur:
                return g.push
        return 0.0

    def breeze(self) -> float:
        a, b = self.phase
        return self.level.breeze * (0.7 * math.sin(0.45 * self.t + a)
                                    + 0.5 * math.sin(1.1 * self.t + b))

    def wind(self) -> float:
        return self.gust() + self.breeze()

    def swing_push(self) -> float:
        """The wire's sideways acceleration, and so its shove on you."""
        return (-STIFF * self.swing - 0.8 * self.swing_v
                - 2.0 * self.level.spring * math.sin(self.lean))

    def tip(self) -> float:
        return self.level.tip * (1.0 + 2.0 * abs(self.boing))

    def outside(self) -> float:
        """Everything but the pole and the lean that pushes you over."""
        return (self.wind() + self.level.sway * math.sin(self.t * 1.7)
                + 1.2 * sum(self.perched) - 0.25 * self.swing_push())

    def bird_spot(self, end: int) -> Tuple[float, float]:
        """Where a bird on that end of the pole is on the screen."""
        x = H.W / 2 + REACH * (self.pole() * 0.35 + end * PERCH)
        return x, 250.0 - (x - H.W / 2) * math.tan(self.lean) * 0.5

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        for end in list(self.perched):
            bx, by = self.bird_spot(end)
            if math.hypot(self.hand.x - bx, self.hand.y - by) <= 34.0:
                self.perched.remove(end)
                self.note(0.2, 1400.0, BIRD, 0.4, pan=end * 0.7)
                return

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if self.result is not None or port != STEP or self.t < self.rest:
            return
        self.rest = self.t + 0.35
        self.taken += 1
        self.foot = -self.foot
        slip = 3.0 if abs(self.lean) > 0.3 else 1.0
        self.rate += self.foot * self.level.jolt * slip
        self.swing_v += self.foot * 0.3 * self.level.spring
        self.boing_v -= self.level.bounce
        self.note(0.06, 240.0, TICK, 0.4)
        if self.taken >= self.level.steps:
            self.note(0.4, 880.0, DONE, 0.5)
            self.result = (True, _('Across'))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        level, walk = self.level, self.walk
        for k, g in enumerate(walk.gusts):
            if not self.warned[k] and self.t >= g.t - 1.0:
                self.warned[k] = True
                self.note(1.0 + g.dur, 200.0, WIND, 0.35,
                          pan=-0.8 if g.push > 0 else 0.8)
        while self.bird_no < len(walk.birds) and \
                walk.birds[self.bird_no][0] <= self.t:
            end = walk.birds[self.bird_no][1]
            self.bird_no += 1
            if end not in self.perched:
                self.perched.append(end)
                self.note(0.25, 1800.0, BIRD, 0.4, pan=end * 0.7)
        self.held += (self.aim() - self.held) * min(1.0, dt / LAG)
        acc = self.swing_push()
        push = self.tip() * math.sin(self.lean) - PULL * self.held \
            + self.outside()
        self.swing_v += acc * dt
        self.swing += self.swing_v * dt
        self.boing_v += (-BOING * self.boing - 1.2 * self.boing_v) * dt
        self.boing += self.boing_v * dt
        self.rate += (push - 0.6 * self.rate) * dt
        self.lean += self.rate * dt
        if abs(self.lean) > 0.35 and self.t >= self.creak_at:
            self.creak_at = self.t + 0.4
            self.note(0.2, 300.0, CREAK, 0.3,
                      pan=0.6 if self.lean > 0 else -0.6)
        if abs(self.lean) >= FALL:
            self.note(0.6, 70.0, FELL, 0.6)
            self.result = (False, _('You fell'))
        elif self.t >= self.end:
            self.result = (False, _('Out of time on the wire'))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Hold the pole where it rights the lean, step when steady, and
    reach for a bird when there is room to: one port a step."""
    if run.result is not None:
        return []
    hand, level = run.hand, run.level
    if hand.down:
        return [H.RELEASE]
    steady = abs(run.lean) < 0.08 and abs(run.rate) < 0.25
    if run.perched and abs(run.lean) < 0.2 and abs(run.rate) < 0.5:
        end = run.perched[0]
        bx, by = run.bird_spot(end)
        if abs(hand.x - bx) <= 28.0 and abs(hand.y - by) <= 20.0:
            return [H.PRESS]
        if abs(hand.y - by) > 20.0:
            return [H.toward(hand, hand.x, by, tol=15.0)]
        return [9 if bx > hand.x else 6]              # a long step across
    want = (run.tip() * math.sin(run.lean) + run.outside() + 9.0 * run.lean
            + 5.0 * run.rate) / PULL
    want = max(-1.0, min(1.0, want))
    lead = run.held + 2.5 * (want - run.held)     # the pole is slow: hurry it
    x = H.W / 2 + REACH * max(-1.0, min(1.0, lead))
    if abs(hand.x - x) > 12.0:
        return [H.toward(hand, x, hand.y, tol=6.0)]
    if steady and run.t >= run.rest:
        return [STEP]
    move = H.toward(hand, x, 250.0, tol=6.0)
    return [move] if move is not None else []


def play(walk: Walk, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(walk), pilot, EVENTS, act, dt)
