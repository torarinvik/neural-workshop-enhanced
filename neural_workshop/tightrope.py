# -*- coding: utf-8 -*-
"""Tightrope: walk the wire with a balance pole.

You are on a wire strung between two towers, high over a city, looking
along it at the far platform, holding a long pole. Move the mouse left
and right and the pole slides that way through your hands -- not at
once, it is heavy and follows the hand a moment behind -- which tips
you back the other way. You can tip forward and back too: every step
lurches you forward, and moving the mouse up carries the pole forward,
which rights you backward (and down carries it back): when you lean left, put the pole out to the right. Up (or
W) takes a step, and each step jolts you a little to one side and then
the other. Lean too far and you are off.

Wind gusts are heard coming -- from the side they will blow from --
before they hit. From rung 10 birds land on the pole and weigh that end
down until you click them off, which means reaching out to them.

The ladder climbs a little every rung, and each new trouble comes in
gently and grows from there:

* rung 1: five steps, soft jolts, a slow lean and plenty of time; every
  rung after adds steps, sharper jolts, quicker tipping and less time;
* from rung 4: the wire sways under you;
* from rung 7: gusts of wind;
* from rung 10: birds on the pole;
* from rung 13: a breeze that never quite stops and keeps changing its
  mind, and pushes you forward and back too;
* from rung 16: the wire is springy and swings sideways under you: your
  steps set it going, leaning shoves it the other way, and its swing
  throws you about in turn;
* from rung 20: the wire bounces too; a high bounce makes every lean
  grow faster and rocks you forward and back.

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
REACH_F = 200.0                # screen units of hand up or down for the
                               # pole right forward or back
PULL_F = 4.0                   # how hard the pole rights a pitch
FALL_P = 0.6                   # radians of pitch that is a fall
LEVEL = 250.0                  # the pole's height on the screen, centred
FWD_PX = 60.0                  # how far up the pole shows, right forward
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
    tip_p: float               # how fast a pitch forward or back grows
    jolt_p: float              # how hard a step lurches you forward
    seconds: float


def grade(rung: int) -> Grade:
    """Every rung a little harder than the one below; each new trouble
    comes in gently at its rung and grows from there."""
    r = max(1, int(rung))
    k = r - 1

    def grow(start: int, first: float, per: float, cap: float) -> float:
        return 0.0 if r < start else min(cap, first + per * (r - start))
    steps = min(40, 5 + (2 * k) // 3)
    return Grade(
        rung=r, steps=steps,
        jolt=min(0.7, 0.12 + 0.025 * k),
        tip=min(4.6, 1.5 + 0.11 * k),
        sway=grow(4, 0.12, 0.02, 0.5),
        gusts=0 if r < 7 else min(9, 1 + (r - 7) // 3),
        blow=grow(7, 0.7, 0.05, 1.7),
        birds=0 if r < 10 else min(8, 1 + (r - 10) // 4),
        breeze=grow(13, 0.3, 0.03, 1.0),
        spring=grow(16, 0.5, 0.04, 1.3),
        bounce=grow(20, 0.5, 0.03, 1.1),
        tip_p=min(3.2, 0.8 + 0.09 * k),
        jolt_p=min(0.45, 0.06 + 0.018 * k),
        seconds=steps * max(1.2, 3.6 - 0.08 * k) + 8.0)


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
        self.held_f = 0.0              # how far forward it is, -1 to 1
        self.pitch = 0.0               # radians, positive is forward
        self.prate = 0.0
        self.swing = self.swing_v = 0.0   # the wire sideways
        self.boing = self.boing_v = 0.0   # the wire up and down
        draw = random.Random(walk.seed)
        self.phase = (draw.uniform(0, 6.3), draw.uniform(0, 6.3))

    def aim(self) -> float:
        """Where the hand wants the pole, -1 left to 1 right."""
        return max(-1.0, min(1.0, (self.hand.x - H.W / 2) / REACH))

    def aim_f(self) -> float:
        """How far forward the hand wants the pole, -1 back to 1."""
        return max(-1.0, min(1.0, (self.hand.y - LEVEL) / REACH_F))

    def outside_f(self) -> float:
        """What pitches you forward or back, but the pole and the pitch."""
        return 0.4 * self.breeze() + 0.5 * self.boing_v * self.level.bounce

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
        return x, LEVEL + FWD_PX * self.held_f \
            - (x - H.W / 2) * math.tan(self.lean) * 0.5

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
        self.prate += self.level.jolt_p * (3.0 if abs(self.pitch) > 0.25
                                           else 1.0)
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
        self.held_f += (self.aim_f() - self.held_f) * min(1.0, dt / LAG)
        push_f = self.level.tip_p * math.sin(self.pitch) \
            - PULL_F * self.held_f + self.outside_f()
        self.prate += (push_f - 0.6 * self.prate) * dt
        self.pitch += self.prate * dt
        if abs(self.pitch) > 0.3 and self.t >= self.creak_at:
            self.creak_at = self.t + 0.4
            self.note(0.2, 420.0 if self.pitch > 0 else 220.0, CREAK, 0.3)
        if abs(self.lean) > 0.35 and self.t >= self.creak_at:
            self.creak_at = self.t + 0.4
            self.note(0.2, 300.0, CREAK, 0.3,
                      pan=0.6 if self.lean > 0 else -0.6)
        if abs(self.lean) >= FALL:
            self.note(0.6, 70.0, FELL, 0.6)
            self.result = (False, _('You fell'))
        elif abs(self.pitch) >= FALL_P:
            self.note(0.6, 70.0, FELL, 0.6)
            self.result = (False, _('You fell forward') if self.pitch > 0
                           else _('You fell backward'))
        elif self.t >= self.end:
            self.result = (False, _('Out of time on the wire'))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Hold the pole where it rights the lean (left and right) and the
    pitch (forward and back), step when steady, and reach for a bird
    when there is room to: one port a step."""
    if run.result is not None:
        return []
    hand = run.hand
    if hand.down:
        return [H.RELEASE]
    steady = abs(run.lean) < 0.08 and abs(run.rate) < 0.25 and \
        abs(run.pitch) < 0.08 and abs(run.prate) < 0.25
    want = (run.tip() * math.sin(run.lean) + run.outside() + 9.0 * run.lean
            + 5.0 * run.rate) / PULL
    want = max(-1.0, min(1.0, want))
    lead = run.held + 2.5 * (want - run.held)     # the pole is slow: hurry it
    x = H.W / 2 + REACH * max(-1.0, min(1.0, lead))
    want_f = (run.level.tip_p * math.sin(run.pitch) + run.outside_f()
              + 7.0 * run.pitch + 4.0 * run.prate) / PULL_F
    want_f = max(-1.0, min(1.0, want_f))
    lead_f = run.held_f + 2.5 * (want_f - run.held_f)
    y = LEVEL + REACH_F * max(-1.0, min(1.0, lead_f))
    calm = abs(run.lean) < 0.2 and abs(run.rate) < 0.5 and \
        abs(run.pitch) < 0.15 and abs(run.prate) < 0.4
    if run.perched and calm:
        end = run.perched[0]
        bx, by = run.bird_spot(end)
        if abs(hand.x - bx) <= 28.0 and abs(hand.y - by) <= 20.0:
            return [H.PRESS]
        if abs(hand.y - by) > 20.0:
            return [H.toward(hand, hand.x, by, tol=15.0)]
        return [9 if bx > hand.x else 6]              # a long step across
    ex, ey = abs(hand.x - x) / REACH, abs(hand.y - y) / REACH_F
    if max(ex, ey) > 0.03:
        if ex >= ey:
            return [H.toward(hand, x, hand.y, tol=6.0)]
        return [H.toward(hand, hand.x, y, tol=6.0)]
    if steady and run.t >= run.rest:
        return [STEP]
    return []


def play(walk: Walk, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(walk), pilot, EVENTS, act, dt)
