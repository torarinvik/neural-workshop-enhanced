# -*- coding: utf-8 -*-
"""Lander: bring a craft down onto a pad, gently and upright.

Two dimensions of plain physics: gravity pulls down, the engine pushes
along the craft's axis while it fires, the craft turns while a turn is
held, and wind pushes sideways. A landing counts on the pad, slower
than the rung's limits down and across, and near upright; anywhere else
the craft is lost.

* rungs 1-3: moon gravity, a wide pad below, no fuel limit;
* rungs 4-6: the pad off to one side, the craft moving at the start,
  fuel for 25 seconds of firing, tighter limits;
* rungs 7-9: rough ground with the pad on a shelf, a narrower pad;
* rungs 10-12: a steady wind;
* rungs 13-15: gusts that rise and fall;
* rungs 16-19: **gravity and the engine's strength are hidden**, a new
  pair every landing -- found out from how the craft answers;
* from rung 20 the pad **moves** -- speed across is then judged
  against the pad's -- narrower, with less fuel and stricter
  limits every rung.

The craft's speeds, tilt and fuel are shown, as instruments would. A
trial is landed or lost. Clocked: it is flying.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

WORLD_W, WORLD_H = 100.0, 70.0
#: How fast the craft turns while a turn is held, radians a second.
TURN = 2.2
#: Half the craft's width, and its height (its feet are at y).
HALF_W, HIGH = 1.6, 3.2
SECONDS = 60.0
#: Seconds the moving pad takes to go there and back.
PAD_PERIOD = 16.0

THRUST, LEFT, RIGHT, THRUST_LEFT, THRUST_RIGHT = range(5)


class Grade(NamedTuple):
    rung: int
    pad: float
    offset: Tuple[float, float]
    start_speed: float
    fuel: Optional[float]
    rough: bool
    wind: float
    gusts: bool
    hidden: bool
    moving: float
    max_down: float
    max_across: float
    max_tilt: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        pad=24.0 if r < 4 else (16.0 if r < 7 else
                                (12.0 if r < 20 else max(6.0, 9.0 - 0.3 * top))),
        offset=(0.0, 5.0 + 5.0 * (r - 1)) if r < 4 else (20.0, 32.0),
        start_speed=0.0 if r < 4 else 3.0,
        fuel=None if r < 4 else (25.0 if r < 20 else max(15.0, 22.0 - 0.4 * top)),
        rough=r >= 7,
        wind=0.0 if r < 10 else 0.5,
        gusts=r >= 13,
        hidden=r >= 16,
        moving=0.0 if r < 20 else 8.0,
        max_down=3.5 if r < 4 else (3.0 if r < 7 else
                                    (2.5 if r < 20 else max(1.4, 2.0 - 0.06 * top))),
        max_across=2.0 if r < 4 else 1.5,
        max_tilt=math.radians(15 if r < 4 else (12 if r < 20 else 8)))


class Flight(NamedTuple):
    rung: int
    level: Grade
    gravity: float
    #: The engine's push, as a multiple of gravity.
    ratio: float
    ground: Tuple[Tuple[float, float], ...]
    pad_x: float
    pad_y: float
    start: Tuple[float, float, float, float]
    wind: float
    wind_phase: float


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Flight:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    gravity, ratio = 1.62, 2.6
    if level.hidden:
        gravity = draw.uniform(1.0, 3.7)
        ratio = draw.uniform(1.8, 3.0)
    pad_x = draw.uniform(25.0, 75.0)
    pad_y = draw.uniform(4.0, 16.0) if level.rough else 4.0
    if level.moving:
        pad_x = 50.0
        pad_y = 4.0
    ground = []
    x = 0.0
    while x <= WORLD_W + 1e-9:
        if abs(x - pad_x) <= level.pad / 2 + level.moving + 2.5:
            y = pad_y
        elif level.rough and not level.moving:
            y = draw.uniform(2.0, pad_y + 14.0)
        else:
            y = 4.0
        ground.append((x, y))
        x += 5.0
    # The pad's own flat stretch, set into the ground exactly.
    half = level.pad / 2 + level.moving
    ground = [p for p in ground if abs(p[0] - pad_x) > half + 0.01]
    ground += [(pad_x - half, pad_y), (pad_x + half, pad_y)]
    ground.sort()
    side = draw.choice((-1, 1))
    off = draw.uniform(*level.offset) * side
    sx = max(8.0, min(WORLD_W - 8.0, pad_x + off))
    svx = -side * draw.uniform(0, level.start_speed)
    wind = level.wind * draw.choice((-1, 1)) * draw.uniform(0.6, 1.2)
    return Flight(level.rung, level, gravity, ratio, tuple(ground), pad_x,
                  pad_y, (sx, WORLD_H - 12.0, svx, 0.0), wind,
                  draw.uniform(0, 2 * math.pi))


def ground_at(flight: Flight, x: float) -> float:
    pts = flight.ground
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / ((x1 - x0) or 1.0)
    return pts[-1][1]


def pad_centre(flight: Flight, t: float) -> float:
    if not flight.level.moving:
        return flight.pad_x
    return flight.pad_x + flight.level.moving * math.sin(2 * math.pi * t
                                                         / PAD_PERIOD)


def pad_speed(flight: Flight, t: float) -> float:
    if not flight.level.moving:
        return 0.0
    w = 2 * math.pi / PAD_PERIOD
    return flight.level.moving * w * math.cos(w * t)


def wind_at(flight: Flight, t: float) -> float:
    if not flight.level.gusts:
        return flight.wind
    return flight.wind * (1.0 + 0.8 * math.sin(0.7 * t + flight.wind_phase)
                          + 0.4 * math.sin(2.3 * t + 2 * flight.wind_phase))


class Craft:
    """The craft in flight: one step of physics at a time."""

    def __init__(self, flight: Flight) -> None:
        self.flight = flight
        self.x, self.y, self.vx, self.vy = flight.start
        self.angle = 0.0
        self.fuel = flight.level.fuel
        self.t = 0.0
        self.firing = False
        self.result: Optional[Tuple[bool, str]] = None

    def step(self, dt: float, control: Optional[int]) -> None:
        if self.result is not None:
            return
        f = self.flight
        turn = {LEFT: 1, THRUST_LEFT: 1, RIGHT: -1, THRUST_RIGHT: -1}.get(
            control, 0)
        fire = control in (THRUST, THRUST_LEFT, THRUST_RIGHT)
        if self.fuel is not None and self.fuel <= 0:
            fire = False
        self.firing = fire
        self.angle = max(-math.pi / 2, min(math.pi / 2,
                                           self.angle + turn * TURN * dt))
        ax = wind_at(f, self.t)
        ay = -f.gravity
        if fire:
            push = f.gravity * f.ratio
            ax += -math.sin(self.angle) * push
            ay += math.cos(self.angle) * push
            if self.fuel is not None:
                self.fuel = max(0.0, self.fuel - dt)
        self.vx += ax * dt
        self.vy += ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.t += dt
        self._check()

    def _check(self) -> None:
        f = self.flight
        level = f.level
        if not -5 <= self.x <= WORLD_W + 5 or self.y > WORLD_H + 20:
            self.result = (False, _('Flew off the map'))
            return
        if self.t >= SECONDS:
            self.result = (False, _('Out of time'))
            return
        feet = [self.x + dx * math.cos(self.angle) for dx in (-HALF_W,
                                                              HALF_W)]
        if self.y > max(ground_at(f, x) for x in feet + [self.x]):
            return
        on_pad = abs(self.x - pad_centre(f, self.t)) <= level.pad / 2 - 0.5 \
            and abs(ground_at(f, self.x) - f.pad_y) < 0.01
        if not on_pad:
            self.result = (False, _('Came down off the pad'))
        elif -self.vy > level.max_down:
            self.result = (False, _('Too fast down: %.1f m/s (limit %.1f)')
                           % (-self.vy, level.max_down))
        elif abs(self.vx - pad_speed(f, self.t)) > level.max_across:
            # Across the pad, not across the ground: it may be moving.
            self.result = (False, _('Too fast across: %.1f m/s (limit %.1f)')
                           % (abs(self.vx - pad_speed(f, self.t)),
                              level.max_across))
        elif abs(self.angle) > level.max_tilt:
            self.result = (False, _('Tilted %d degrees (limit %d)')
                           % (round(math.degrees(abs(self.angle))),
                              round(math.degrees(level.max_tilt))))
        else:
            self.result = (True, _('Landed: %.1f m/s down') % -self.vy)


def autopilot(craft: Craft) -> Optional[int]:
    """A controller that knows gravity, the engine and the wind: proof
    that a rung can be flown."""
    f = craft.flight
    level = f.level
    push = f.gravity * f.ratio
    t = craft.t
    lead = 1.5
    near = abs(craft.x - pad_centre(f, t)) < level.pad
    target = pad_centre(f, t if near else t + lead)
    pad_v = pad_speed(f, t)
    height = craft.y - f.pad_y
    # Stay high until over the pad, and above rough ground on the way.
    away = abs(craft.x - target)
    clear = max(ground_at(f, x) for x in
                (craft.x - 6, craft.x, craft.x + 6, craft.x + craft.vx * 2))
    gain = 0.8 if level.moving else 0.35
    want_vx = max(-6.0, min(6.0, gain * (target - craft.x))) + pad_v
    settled = abs(craft.vx - pad_v) < 1.0
    if away > level.pad / 2 - 1.5 or (level.moving and not settled):
        floor_y = max(clear + 6.0, f.pad_y + 8.0)
        want_vy = max(-3.0, 0.8 * (floor_y - craft.y))
    else:
        want_vy = -max(0.6 * level.max_down, min(6.0, 0.4 * height))
    ax = 1.2 * (want_vx - craft.vx) - wind_at(f, t)
    ay = 1.5 * (want_vy - craft.vy) + f.gravity
    ay = max(0.05, ay)
    want_angle = math.atan2(-ax, ay)
    limit = 0.6 if height > (2.5 if level.moving else 6) else \
        level.max_tilt * 0.5
    want_angle = max(-limit, min(limit, want_angle))
    need = math.hypot(ax, ay)
    # Fire on what the vertical needs; sideways comes from the tilt.
    fire = ay > 0.5 * push * math.cos(craft.angle) or \
        craft.vy < want_vy - 0.3
    del need
    if craft.fuel is not None and craft.fuel <= 0:
        fire = False
    err = want_angle - craft.angle
    turn = 0 if abs(err) < TURN / 60.0 else (1 if err > 0 else -1)
    if fire:
        return {0: THRUST, 1: THRUST_LEFT, -1: THRUST_RIGHT}[turn]
    return {0: None, 1: LEFT, -1: RIGHT}[turn]


def fly(flight: Flight, pilot, dt: float = 1 / 60.0) -> Tuple[bool, str]:
    craft = Craft(flight)
    while craft.result is None:
        craft.step(dt, pilot(craft))
    return craft.result
