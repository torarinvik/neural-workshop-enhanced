# -*- coding: utf-8 -*-
"""Juggler: keep every ball in the air until the act is over.

Balls fall under gravity inside a circus ring with walls either side
and a canvas roof. The performer slides a tray along the floor; a ball
that lands on the tray is tossed back up -- always to the same height,
but steered by where on the tray it lands: off the left end it flies
left, off the right end right. Every toss stays up the same time, so
heavy balls fly low and light ones high. A ball that reaches the floor
ends the act.

The ladder:

* rungs 1-3: one ball, then two;
* rungs 4-6: three balls;
* rungs 7-9: heavy and light balls -- each falls at its own pace;
* rungs 10-12: four balls;
* rungs 13-15: a draught blows across the ring;
* rungs 16-19: a narrower tray;
* from rung 20: five balls, a longer act, a smaller tray.

Pass: no ball dropped before the act ends.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

LEFT, RIGHT = range(2)
PORTS = 2
EVENTS = ()
WORLD_W, WORLD_H = 32.0, 24.0
TRAY_Y = 1.6
RADIUS = 0.6
G = 9.0
FLIGHT = 3.4             # seconds every toss spends in the air
PUSH = 70.0              # tray acceleration
BRAKE = 60.0
TOP = 20.0               # tray top speed


class Grade(NamedTuple):
    rung: int
    balls: int
    mixed: bool
    draught: float
    tray: float
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    balls = (1 if r < 2 else 2 if r < 4 else 3 if r < 10 else 4 if r < 20
             else 5)
    return Grade(
        rung=r, balls=balls, mixed=r >= 7,
        draught=0.0 if r < 13 else 0.9 + 0.05 * top,
        tray=5.0 if r < 16 else 4.2 if r < 20 else max(3.0, 3.8 - 0.06 * top),
        seconds=25.0 + 3.0 * balls + (0.6 * top))


class Act(NamedTuple):
    level: Grade
    drops: List[Tuple[float, float]]     # (time, x) each ball comes in
    weights: List[float]                 # gravity factor per ball
    draught_seed: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Act:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        act_ = _build(level, draw)
        best = best or act_
        if play(act_)[0]:
            return act_
    return best


def _build(level: Grade, draw: random.Random) -> Act:
    weights = [draw.choice((0.7, 1.0, 1.35)) if level.mixed else 1.0
               for _k in range(level.balls)]
    # Each ball first reaches the tray a fair share of a beat after the
    # last, whatever it weighs.
    drops = []
    for k, w in enumerate(weights):
        lands = 2.8 + k * FLIGHT / level.balls * draw.uniform(0.9, 1.1)
        fall = math.sqrt(2 * (WORLD_H - 1.0 - TRAY_Y - RADIUS) / (G * w))
        drops.append((round(max(0.0, lands - fall), 2),
                      draw.uniform(8.0, WORLD_W - 8.0)))
    return Act(level, drops, weights, draw.randrange(1 << 20))


class Ball:
    def __init__(self, x: float, weight: float) -> None:
        self.x, self.y = x, WORLD_H - 1.0
        self.vx, self.vy = 0.0, 0.0
        self.weight = weight
        self.live = False
        self.catches = 0
        self.trail: List[Tuple[float, float]] = []

    @property
    def g(self) -> float:
        return G * self.weight


class Run:
    def __init__(self, act_: Act) -> None:
        self.act = act_
        self.level = act_.level
        self.t = 0.0
        self.x = WORLD_W / 2
        self.v = 0.0
        self.balls = [Ball(x, w) for (_t, x), w in zip(act_.drops,
                                                       act_.weights)]
        self.result: Optional[Tuple[bool, str]] = None
        self.flashes: List[Tuple[float, float]] = []

    def draught(self, t: Optional[float] = None) -> float:
        if not self.level.draught:
            return 0.0
        t = self.t if t is None else t
        k = self.act.draught_seed % 13
        return self.level.draught * math.sin(t * 0.3 + k)

    def toss_speed(self, ball: Ball) -> float:
        """Every toss is in the air the same time: a heavy ball flies
        lower, a light one higher, and the rhythm holds."""
        return ball.g * FLIGHT / 2

    def step(self, dt: float, control: Optional[int]) -> None:
        if self.result is not None:
            return
        self.t += dt
        level = self.level
        if control == LEFT:
            self.v = max(-TOP, self.v - PUSH * dt)
        elif control == RIGHT:
            self.v = min(TOP, self.v + PUSH * dt)
        else:
            slow = BRAKE * dt
            self.v = 0.0 if abs(self.v) <= slow else \
                self.v - math.copysign(slow, self.v)
        self.x += self.v * dt
        half = level.tray / 2
        if self.x < half or self.x > WORLD_W - half:
            self.x = max(half, min(WORLD_W - half, self.x))
            self.v = 0.0
        wind = self.draught()
        for k, b in enumerate(self.balls):
            if not b.live:
                if self.t >= self.act.drops[k][0]:
                    b.live = True
                continue
            b.vy -= b.g * dt
            b.vx += wind * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.x < RADIUS or b.x > WORLD_W - RADIUS:
                b.x = max(RADIUS, min(WORLD_W - RADIUS, b.x))
                b.vx = -b.vx
            if b.y > WORLD_H - RADIUS and b.vy > 0:
                b.y = WORLD_H - RADIUS
                b.vy = -b.vy
            if b.vy < 0 and TRAY_Y <= b.y - RADIUS + 0.0 < TRAY_Y + 0.6 \
                    and abs(b.x - self.x) <= half + RADIUS * 0.5:
                off = (b.x - self.x) / half
                b.vy = self.toss_speed(b)
                b.vx = max(-9.0, min(9.0, off * 6.0 + self.v * 0.25))
                b.y = TRAY_Y + RADIUS
                b.catches += 1
                self.flashes.append((self.t, b.x))
                del self.flashes[:-8]
            if b.y < RADIUS:
                self.result = (False, _('A ball hit the floor'))
                return
            if not b.trail or abs(b.trail[-1][1] - b.y) + abs(
                    b.trail[-1][0] - b.x) > 0.7:
                b.trail.append((b.x, b.y))
                del b.trail[:-8]
        if self.t >= level.seconds:
            self.result = (True, _('%d balls kept up for %.0f s') % (
                len(self.balls), level.seconds))


# --- the reference performer ----------------------------------------------------

def landing(run: Run, b: Ball) -> Tuple[float, float]:
    """(seconds until, x) where ball *b* comes down to the tray,
    walls and draught included, by stepping it forward."""
    x, y, vx, vy = b.x, b.y, b.vx, b.vy
    if not b.live:
        wait = run.act.drops[run.balls.index(b)][0] - run.t
        x, y, vx, vy = b.x, b.y, 0.0, 0.0
    else:
        wait = 0.0
    t, dt = 0.0, 1 / 30.0
    while t < 8.0:
        vy -= b.g * dt
        vx += run.draught(run.t + wait + t) * dt
        x += vx * dt
        y += vy * dt
        if x < RADIUS or x > WORLD_W - RADIUS:
            x = max(RADIUS, min(WORLD_W - RADIUS, x))
            vx = -vx
        if y > WORLD_H - RADIUS and vy > 0:
            vy = -vy
        t += dt
        if vy < 0 and y - RADIUS <= TRAY_Y + 0.3:
            return wait + t, x
    return wait + t, x


def autopilot(run: Run) -> List[int]:
    """Be under the next ball to come down, a little to the side that
    sends it back toward the middle."""
    if run.result is not None:
        return []
    soon = sorted(landing(run, b) for b in run.balls)
    if soon[0][0] < 0.02 and len(soon) > 1:
        soon = soon[1:]      # caught, or past saving: the next counts
    when, lx = soon[0]
    half = run.level.tray / 2
    # Catch it off-centre by just enough to send it back to the middle.
    aim = WORLD_W / 2 + (lx - WORLD_W / 2) * 0.2
    off = max(-0.85, min(0.85, (aim - lx) / FLIGHT / 6.0))
    target = lx - off * half
    # Speed wanted: get there in time, braking distance in mind.
    err = target - run.x
    want = max(-TOP, min(TOP, err * 9.0))
    if want > run.v + 1.0:
        return [RIGHT]
    if want < run.v - 1.0:
        return [LEFT]
    return []


def act(run: Run, port: int) -> None:
    pass


def play(act_: Act, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(act_)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
