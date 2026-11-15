# -*- coding: utf-8 -*-
"""Catch: run a basket under balls lobbed down a court.

A court runs away from the player; at the far end a thrower lobs balls
toward the near end, high and slow or flat and fast. Move the basket
over the floor -- with the mouse, or the arrow keys -- to wherever a
ball will come down, and be there when it does. Every ball whistles as
it flies, from wherever it is, higher the higher it is, louder the
nearer; it pops when thrown and thuds when it lands.

Depth is the whole difficulty: on the screen a ball that will land near
and one that will land far trace almost the same curve. A shadow on the
floor gives it away at first; later the arc, the ball's size and the
sound are all there is.

The ladder:

* rungs 1-3: one basket, slow high lobs one at a time, the shadow shown;
* rungs 4-6: quicker, flatter throws, a smaller basket;
* rungs 7-9: no shadow; balls spin and curve sideways;
* rungs 10-12: balls bounce off the side walls, two in the air at once;
* rungs 13-15: two baskets -- red on the keys, blue on the mouse -- each
  catching only balls of its own colour;
* rungs 16-19: fog over the far half of the court: listen for the throw;
* from rung 20: the view swings to and fro, wind, smaller baskets, more
  balls every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Set, Tuple

from .drshape import Note
from .i18n import _

LEFT, RIGHT, NEAR, FAR = 0, 1, 2, 3
PORTS = 8                      # 0-3 the first basket, 4-7 the second
EVENTS = ()
HALF = 10.0                    # the court is x in [-HALF, HALF]
LONG = 40.0                    # the thrower stands at z = LONG
ZONE = (-8.5, 8.5, 2.0, 15.0)  # where a basket may go: x0, x1, z0, z1
FOG = 21.0                     # nothing beyond this shows in fog
G = 9.8
RIM = 0.6                      # the basket's rim height
SPEED = 12.0                   # how fast a basket moves


class Grade(NamedTuple):
    rung: int
    balls: int
    misses: int                # misses allowed
    flight: Tuple[float, float]
    radius: float
    shadow: bool
    spin: float                # sideways acceleration, at most
    walls: bool
    overlap: float             # next throw after this share of a flight
    two: bool
    fog: bool
    swing: float               # degrees the view swings
    wind: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        balls=5 if r < 4 else 6 if r < 13 else 8 if r < 20
        else min(14, 8 + top // 2),
        misses=1,
        flight=((2.0, 2.5) if r < 4 else (1.5, 2.0) if r < 20
                else (max(1.1, 1.4 - 0.03 * top), max(1.5, 1.9 - 0.03 * top))),
        radius=(2.3 if r < 4 else 1.9 if r < 7 else 1.7 if r < 13
                else 1.6 if r < 20 else max(1.1, 1.5 - 0.04 * top)),
        shadow=r < 7,
        spin=0.0 if r < 7 else 5.0,
        walls=r >= 10,
        overlap=1.3 if r < 10 else 0.6 if r < 20 else max(0.35,
                                                           0.55 - 0.02 * top),
        two=r >= 13,
        fog=r >= 16,
        swing=0.0 if r < 20 else min(35.0, 18.0 + 2 * top),
        wind=0.0 if r < 20 else min(4.0, 1.5 + 0.25 * top))


class Ball(NamedTuple):
    t0: float                  # thrown
    x0: float
    y0: float
    v: Tuple[float, float, float]
    ax: float                  # sideways acceleration (spin and wind)
    flight: float              # seconds to the rim
    land: Tuple[float, float]  # (x, z) where it comes down to the rim
    colour: int                # 0 red, 1 blue


class Court(NamedTuple):
    level: Grade
    balls: List[Ball]
    start: List[Tuple[float, float]]    # each basket's start


def fold(u: float) -> float:
    """*u* reflected back and forth between the side walls."""
    w = 4 * HALF
    v = (u + HALF) % w
    if v > 2 * HALF:
        v = w - v
    return v - HALF


def where(ball: Ball, t: float, walls: bool = True
          ) -> Tuple[float, float, float]:
    """The ball at time *t* (x, y, z), before or after its throw."""
    s = max(0.0, t - ball.t0)
    vx, vy, vz = ball.v
    u = ball.x0 + vx * s + 0.5 * ball.ax * s * s
    y = ball.y0 + vy * s - 0.5 * G * s * s
    return (fold(u) if walls else u, max(0.0, y), LONG + vz * s)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Court:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        court = _build(level, draw)
        best = best or court
        if play(court)[0]:
            return court
    return best


def _build(level: Grade, draw: random.Random) -> Court:
    balls: List[Ball] = []
    t = 1.2
    x0z, x1z, z0z, z1z = ZONE
    wind = draw.uniform(-level.wind, level.wind)
    last = None
    for k in range(level.balls):
        T = draw.uniform(*level.flight)
        lx = draw.uniform(x0z + 0.5, x1z - 0.5)
        lz = draw.uniform(z0z + 0.5, z1z - 0.5)
        if last is not None and not level.two:
            # Far enough from the last that it has to be run to.
            for _try in range(20):
                if math.hypot(lx - last[0], lz - last[1]) > 5.0:
                    break
                lx = draw.uniform(x0z + 0.5, x1z - 0.5)
                lz = draw.uniform(z0z + 0.5, z1z - 0.5)
        last = (lx, lz)
        x0 = draw.uniform(-HALF * 0.6, HALF * 0.6)
        y0 = 2.0
        ax = draw.uniform(-level.spin, level.spin) + wind
        u = lx
        if level.walls and draw.random() < 0.6:
            u = 2 * HALF - lx if draw.random() < 0.5 else -2 * HALF - lx
        vx = (u - x0 - 0.5 * ax * T * T) / T
        vy = (RIM - y0 + 0.5 * G * T * T) / T
        vz = (lz - LONG) / T
        colour = draw.randrange(2) if level.two else 0
        balls.append(Ball(round(t, 3), x0, y0, (vx, vy, vz), ax, T,
                          (lx, lz), colour))
        t += T * level.overlap + draw.uniform(0.2, 0.6)
    starts = [(-3.0, 6.0), (3.0, 6.0)] if level.two else [(0.0, 6.0)]
    return Court(level, balls, starts)


def _on(control) -> Set[int]:
    if control is None:
        return set()
    if isinstance(control, int):
        return {control}
    return set(control)


class Run:
    def __init__(self, court: Court) -> None:
        self.court = court
        self.level = court.level
        self.t = 0.0
        self.baskets = [list(p) for p in court.start]
        #: Where the mouse wants a basket, if anywhere: (x, z) or None.
        self.aim: List[Optional[Tuple[float, float]]] = [None] * len(
            self.baskets)
        self.fate: List[Optional[bool]] = [None] * len(court.balls)
        self.caught = 0
        self.missed = 0
        self.result: Optional[Tuple[bool, str]] = None

    def mouse_basket(self) -> int:
        return len(self.baskets) - 1

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        on = _on(control)
        x0z, x1z, z0z, z1z = ZONE
        for b, basket in enumerate(self.baskets):
            dx = dz = 0.0
            base = 4 * b
            if base + LEFT in on:
                dx -= 1
            if base + RIGHT in on:
                dx += 1
            if base + NEAR in on:
                dz -= 1
            if base + FAR in on:
                dz += 1
            if dx or dz:
                basket[0] += dx * SPEED * dt
                basket[1] += dz * SPEED * dt
            elif self.aim[b] is not None:
                ax, az = self.aim[b]
                ex, ez = ax - basket[0], az - basket[1]
                d = math.hypot(ex, ez)
                if d > 1e-6:
                    move = min(d, SPEED * dt)
                    basket[0] += ex / d * move
                    basket[1] += ez / d * move
            basket[0] = max(x0z, min(x1z, basket[0]))
            basket[1] = max(z0z, min(z1z, basket[1]))
        walls = self.level.walls
        for k, ball in enumerate(self.court.balls):
            if self.fate[k] is not None or self.t < ball.t0 + ball.flight:
                continue
            x, _y, z = where(ball, ball.t0 + ball.flight, walls)
            basket = self.baskets[ball.colour if self.level.two else 0]
            ok = math.hypot(x - basket[0], z - basket[1]) <= \
                self.level.radius
            self.fate[k] = ok
            if ok:
                self.caught += 1
            else:
                self.missed += 1
        if self.missed > self.level.misses:
            self.result = (False, _('%d balls dropped') % self.missed)
        elif all(f is not None for f in self.fate):
            self.result = (True, _('%d of %d caught') % (
                self.caught, len(self.fate)))

    def in_air(self) -> List[int]:
        return [k for k, b in enumerate(self.court.balls)
                if self.fate[k] is None and self.t >= b.t0]


#: The patches :func:`sounds` voices its notes with, by index.
PATCHES = ('pluck', 'flute', 'wood')


def sounds(court: Court) -> List[Note]:
    """Every ball pops when thrown, whistles as it flies -- from where it
    is, higher the higher it is, louder the nearer -- and thuds down."""
    out: List[Note] = []
    seed = 0
    walls = court.level.walls
    for ball in court.balls:
        seed += 1
        out.append(Note(ball.t0, 0.08, 330.0, ball.x0 / HALF,
                        ball.x0 / HALF, 0.35, 0.35, 0.9, 0, seed, -1, 0.0))
        s = 0.06
        while s < ball.flight:
            x, y, z = where(ball, ball.t0 + s, walls)
            x2, y2, z2 = where(ball, ball.t0 + s + 0.08, walls)
            g = 0.06 + 0.3 * (1.0 - z / LONG)
            g2 = 0.06 + 0.3 * (1.0 - z2 / LONG)
            seed += 1
            out.append(Note(ball.t0 + s, 0.09, 500.0 + 60.0 * y,
                            x / HALF, x2 / HALF, g, g2, 0.6, 1, seed, -1,
                            0.0))
            s += 0.08
        x, _y, _z = where(ball, ball.t0 + ball.flight, walls)
        seed += 1
        out.append(Note(ball.t0 + ball.flight + 0.06, 0.12, 110.0, x / HALF,
                        x / HALF, 0.45, 0.45, 0.5, 2, seed, -1, 0.0))
    out.sort(key=lambda n: n.t)
    return out


def act(run: Run, port: int) -> None:
    pass


def autopilot(run: Run) -> List[int]:
    """Each basket runs to where the next ball of its own colour comes
    down -- worked out from the throw, as a catcher's eye does."""
    out = []
    walls = run.level.walls
    for b, basket in enumerate(run.baskets):
        mine = [ball for k, ball in enumerate(run.court.balls)
                if run.fate[k] is None and
                (ball.colour == b or not run.level.two)]
        if not mine:
            continue
        ball = min(mine, key=lambda q: q.t0 + q.flight)
        x, _y, z = where(ball, ball.t0 + ball.flight, walls)
        ex, ez = x - basket[0], z - basket[1]
        if abs(ex) > 0.12:
            out.append(4 * b + (RIGHT if ex > 0 else LEFT))
        if abs(ez) > 0.12:
            out.append(4 * b + (FAR if ez > 0 else NEAR))
    return out


def play(court: Court, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(court)
    while run.result is None:
        run.step(dt, pilot(run))
    return run.result
