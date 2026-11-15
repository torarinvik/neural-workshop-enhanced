# -*- coding: utf-8 -*-
"""Crane: move containers from the ship to their bays without a knock.

A gantry crane runs along an overhead rail. Its trolley drives left
and right, its hoist pays cable out and in, and the hook hangs from
the cable as a pendulum: start or stop the trolley sharply and the
load swings. Each container is painted the colour of the bay it
belongs in. Grab one by lowering the hook onto its roof; release it
low over a bay and it settles onto whatever is there.

Fails: a carried container striking a stack, the hook, or the ground
while still moving fast; a release that misses the bay or comes down
hard; the time running out.

The ladder:

* rungs 1-3: two containers, a short way to go, no swing to speak of
  (a heavy damper on the hook);
* rungs 4-6: three containers, a lighter damper;
* rungs 7-9: a tall stack between ship and bays to clear;
* rungs 10-12: wind pushes the load;
* rungs 13-15: four containers, bays to stack two high in order;
* rungs 16-19: the ship rolls, so the roofs rise and fall;
* from rung 20: gusts, faster trolley, less time, every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

LEFT, RIGHT, UP, DOWN, GRAB = range(5)
PORTS = 5
EVENTS = (GRAB,)
WORLD_W, WORLD_H = 44.0, 24.0
RAIL = 22.0                 # height of the trolley rail
BOX_W, BOX_H = 3.0, 1.6
G = 9.8
SHIP_X = (2.0, 15.0)        # the ship's deck spans these x
DECK = 2.2                  # deck height at rest
PUSH = 3.0                  # trolley motor, m/s^2
FRICTION = 0.8              # trolley rolling to a stop, m/s^2
HOIST = 4.0                 # cable in or out, m/s


class Grade(NamedTuple):
    rung: int
    boxes: int
    damping: float
    wall: float          # height of the stack between, 0 for none
    wind: float          # steady push on the load, m/s^2
    gusts: float
    roll: float          # ship's roll amplitude, m
    speed: float         # trolley top speed
    seconds: float
    two_high: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    boxes = 2 if r < 4 else 3 if r < 13 else 4
    return Grade(
        rung=r, boxes=boxes,
        damping=0.8 if r < 4 else 0.35 if r < 10 else 0.2,
        wall=0.0 if r < 7 else 3 * BOX_H if r < 20 else 4 * BOX_H,
        wind=0.0 if r < 10 else 0.6 + 0.04 * top,
        gusts=0.0 if r < 20 else 0.35 + 0.04 * top,
        roll=0.0 if r < 16 else 0.35 + 0.02 * top,
        speed=5.0 + 0.15 * top,
        seconds=max(90.0, 60.0 * boxes - 2.5 * top),
        two_high=r >= 13)


class Bay(NamedTuple):
    x: float
    colour: int


class Box(NamedTuple):
    colour: int
    x: float           # where it starts, on the ship
    level: int         # how high in its stack, 0 = on the deck


class Yard(NamedTuple):
    level: Grade
    bays: List[Bay]
    boxes: List[Box]
    wall_x: float
    wind_sign: float
    gust_seed: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Yard:
    """A yard the reference crane clears."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(20):
        yard = _build(level, draw)
        best = best or yard
        if play(yard)[0]:
            return yard
    return best


def _build(level: Grade, draw: random.Random) -> Yard:
    n = level.boxes
    colours = list(range(n if not level.two_high else (n + 1) // 2))
    draw.shuffle(colours)
    bay_xs = [41.0 - 4.2 * k for k in range(len(colours))]
    bays = [Bay(x, c) for x, c in zip(bay_xs, colours)]
    paint = [b.colour for b in bays]
    paint = (paint * 2)[:n]
    draw.shuffle(paint)
    # Stacks on the ship, two or three columns.
    cols = [4.5, 8.5, 12.5]
    boxes = []
    heights = [0, 0, 0]
    for c in paint:
        k = draw.randrange(3)
        boxes.append(Box(c, cols[k], heights[k]))
        heights[k] += 1
    return Yard(level, bays, boxes, 22.0 + draw.uniform(-1.5, 1.5),
                draw.choice((-1.0, 1.0)), draw.randrange(1 << 20))


# --- the run ---------------------------------------------------------------------

class Run:
    """The crane and the yard in motion."""

    def __init__(self, yard: Yard) -> None:
        self.yard = yard
        self.level = yard.level
        self.t = 0.0
        self.x = 16.0              # trolley
        self.v = 0.0
        self.cable = 6.0
        self.theta = 0.0           # swing, radians; + swings right
        self.omega = 0.0
        self.held: Optional[int] = None
        # Each box: ('ship', column) / ('bay', bay index) / ('held',)
        self.where: List[Tuple] = [('ship', b.x) for b in yard.boxes]
        self.stack: List[float] = []   # unused, kept for clarity
        self.placed = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.order: List[List[int]] = [[] for _b in yard.bays]
        self.ship_order = {}
        for i, b in enumerate(yard.boxes):
            self.ship_order.setdefault(b.x, []).append(i)
        for col in self.ship_order.values():
            col.sort(key=lambda i: yard.boxes[i].level)
        self.gust = 0.0
        self.last_grab = -1.0

    # --- where things are
    def roll(self, t: Optional[float] = None) -> float:
        t = self.t if t is None else t
        return self.level.roll * math.sin(t * 0.9)

    def hook(self) -> Tuple[float, float]:
        return (self.x + self.cable * math.sin(self.theta),
                RAIL - self.cable * math.cos(self.theta))

    def hook_velocity(self) -> Tuple[float, float]:
        c = self.cable
        return (self.v + c * math.cos(self.theta) * self.omega,
                c * math.sin(self.theta) * self.omega)

    def box_rect(self, i: int) -> Tuple[float, float]:
        """Centre x and bottom y of box *i*."""
        w = self.where[i]
        if w[0] == 'held':
            hx, hy = self.hook()
            return hx, hy - BOX_H
        if w[0] == 'ship':
            col = self.ship_order[w[1]]
            return w[1], DECK + self.roll() + BOX_H * col.index(i)
        bay = self.yard.bays[w[1]]
        return bay.x, BOX_H * self.order[w[1]].index(i)

    def surface(self, x: float, half: float = BOX_W / 2) -> float:
        """The highest roof under a span of x +- half (not the held box)."""
        top = 0.0
        if SHIP_X[0] - half < x < SHIP_X[1] + half:
            top = DECK + self.roll()
        for i in range(len(self.where)):
            if self.where[i][0] == 'held':
                continue
            bx, by = self.box_rect(i)
            if abs(bx - x) < BOX_W / 2 + half - 0.05:
                top = max(top, by + BOX_H)
        if self.level.wall and abs(x - self.yard.wall_x) < 1.6 + half:
            top = max(top, self.level.wall)
        return top

    def grabbable(self) -> Optional[int]:
        hx, hy = self.hook()
        for i, w in enumerate(self.where):
            if w[0] == 'held':
                continue
            if w[0] == 'ship' and self.ship_order[w[1]][-1] != i:
                continue
            if w[0] == 'bay':
                continue
            bx, by = self.box_rect(i)
            if abs(hx - bx) < 0.7 and abs(hy - (by + BOX_H)) < 0.45:
                return i
        return None

    # --- the controls
    def grab(self) -> None:
        if self.result is not None:
            return
        self.last_grab = self.t
        if self.held is None:
            i = self.grabbable()
            if i is not None:
                col = self.ship_order[self.where[i][1]]
                col.remove(i)
                self.where[i] = ('held',)
                self.held = i
            return
        self._release()

    def _release(self) -> None:
        i = self.held
        bx, by = self.box_rect(i)
        below = self.surface(bx)
        vx, vy = self.hook_velocity()
        if by - below > 1.2 or math.hypot(vx, vy) > 1.6:
            self.result = (False, _('A container was dropped hard'))
            return
        for k, bay in enumerate(self.yard.bays):
            if abs(bx - bay.x) < 0.9:
                if bay.colour != self.yard.boxes[i].colour:
                    self.result = (False, _('Wrong bay for that colour'))
                    return
                self.order[k].append(i)
                self.where[i] = ('bay', k)
                self.held = None
                self.placed += 1
                return
        self.result = (False, _('Set down outside a bay'))

    def push(self, t: Optional[float] = None) -> float:
        """The wind on the load now, m/s^2 (positive pushes right)."""
        t = self.t if t is None else t
        level = self.level
        push = level.wind * self.yard.wind_sign
        if level.gusts:
            push += level.gusts * math.sin(t * 0.37 + self.yard.gust_seed
                                           % 7) * self.yard.wind_sign
        return push

    def accel_for(self, control: Optional[int]) -> float:
        """The trolley's acceleration under *control*: the motor pushes
        either way up to top speed; with no command it rolls to a stop."""
        if control == LEFT:
            return -PUSH if self.v > -self.level.speed else 0.0
        if control == RIGHT:
            return PUSH if self.v < self.level.speed else 0.0
        if self.v > 0:
            return -FRICTION
        if self.v < 0:
            return FRICTION
        return 0.0

    def step(self, dt: float, control: Optional[int]) -> None:
        if self.result is not None:
            return
        level = self.level
        self.t += dt
        # Trolley: accelerate toward the commanded speed.
        accel = self.accel_for(control)
        self.v = max(-level.speed, min(level.speed, self.v + accel * dt))
        if control not in (LEFT, RIGHT) and abs(self.v) < FRICTION * dt:
            self.v, accel = 0.0, 0.0
        self.x += self.v * dt
        if self.x < 1.0 or self.x > WORLD_W - 1.0:
            self.x = max(1.0, min(WORLD_W - 1.0, self.x))
            accel, self.v = 0.0, 0.0
        # Hoist.
        if control == UP:
            self.cable = max(2.0, self.cable - HOIST * dt)
        elif control == DOWN:
            self.cable = min(RAIL - 0.3, self.cable + HOIST * dt)
        # Pendulum, pushed by the trolley's acceleration and the wind.
        push = self.push()
        L = self.cable
        alpha = (-(G / L) * math.sin(self.theta)
                 - (accel - push) / L * math.cos(self.theta)
                 - level.damping * self.omega)
        self.omega += alpha * dt
        self.theta += self.omega * dt
        self._collide()
        if self.result is None:
            if self.placed == len(self.yard.boxes):
                self.result = (True, _('All %d containers in their bays')
                               % self.placed)
            elif self.t >= level.seconds:
                self.result = (False, _('Out of time'))

    def _collide(self) -> None:
        hx, hy = self.hook()
        if self.held is not None:
            bx, by = hx, hy - BOX_H
            if by < self.surface(bx) - 0.08:
                vx, vy = self.hook_velocity()
                if math.hypot(vx, vy) > 0.6 or \
                        by < self.surface(bx) - 0.5:
                    self.result = (False, _('The load struck something'))
                    return
                # A gentle touch: it rests there.
                self.cable -= self.surface(bx) - 0.02 - by
        else:
            floor = self.surface(hx, 0.3)
            if hy < floor:
                self.cable -= floor - hy


# --- the reference crane ----------------------------------------------------------

def _next_job(run: Run) -> Optional[Tuple[int, int]]:
    yard = run.yard
    for col in run.ship_order.values():
        if not col:
            continue
        i = col[-1]
        for k, bay in enumerate(yard.bays):
            if bay.colour == yard.boxes[i].colour:
                return i, k
    return None


def _cruise(run: Run) -> float:
    """A cable length that clears everything on the way."""
    top = max(run.surface(x) for x in [0.5 * k for k in range(2, 88)])
    room = RAIL - top - 1.0 - (BOX_H if run.held is not None else 0.0)
    return max(2.0, min(room, 7.0))


def autopilot(run: Run) -> List[int]:
    """Carry the topmost box to its bay with the swing kept small."""
    if run.result is not None:
        return []
    hx, hy = run.hook()
    vx, _vy = run.hook_velocity()
    if run.held is None:
        job = _next_job(run)
        if job is None:
            return []
        i, _k = job
        tx, ty = run.box_rect(i)
        ty += BOX_H
    else:
        k = [k for k, b in enumerate(run.yard.bays)
             if b.colour == run.yard.boxes[run.held].colour][0]
        tx = run.yard.bays[k].x
        ty = run.surface(tx) + BOX_H
    cruise = _cruise(run)
    off = tx - hx
    lean = math.atan2(run.push(), G)
    sway = abs(run.theta - lean) + abs(run.omega) * 0.5
    # High enough to travel?
    if abs(off) > 1.5 and run.cable > cruise + 0.05:
        return [UP]
    if abs(off) > 0.55 or abs(vx) > 0.4 or sway > 0.1:
        return [_drive(run, tx)]
    gap = hy - ty
    if run.held is None:
        if gap > 0.25:
            return [DOWN]
        if run.grabbable() is not None and run.t - run.last_grab > 0.2:
            return [GRAB]
        return [DOWN]
    if gap > 0.12:
        return [DOWN]
    if run.t - run.last_grab > 0.2:
        return [GRAB]
    return []


#: State-feedback gains by cable length, worked out offline as a linear
#: quadratic regulator for the trolley and its pendulum: acceleration
#: = -(k0 (trolley - target) + k1 speed + k2 swing + k3 swing rate).
GAINS = ((2, (0.57, 1.271, -1.169, -0.662)),
         (4, (0.57, 1.35, -1.793, -0.586)),
         (6, (0.57, 1.427, -2.475, -0.301)),
         (9, (0.57, 1.527, -3.308, 0.626)),
         (12, (0.57, 1.611, -3.839, 2.084)),
         (16, (0.571, 1.702, -4.131, 4.684)),
         (21, (0.571, 1.792, -3.97, 8.736)))


def _gains(L: float) -> Tuple[float, ...]:
    for (l0, k0), (l1, k1) in zip(GAINS, GAINS[1:]):
        if L <= l1:
            f = max(0.0, (L - l0) / (l1 - l0))
            return tuple(a + (b - a) * f for a, b in zip(k0, k1))
    return GAINS[-1][1]


def _drive(run: Run, tx: float) -> Optional[int]:
    """Trolley command that brings the hook over *tx* with the swing
    damped: the regulator's acceleration, made of on-off pushes whose
    error carries over to the next frames so they average out."""
    k = _gains(run.cable)
    lean = math.atan2(run.push(), G)
    p = max(-14.0, min(14.0, run.x + run.cable * math.sin(lean) - tx))
    wanted = -(k[0] * p + k[1] * run.v + k[2] * (run.theta - lean)
               + k[3] * run.omega)
    owed = getattr(run, 'owed', 0.0) * 0.98 + wanted
    best, best_err, best_accel = None, None, 0.0
    for port in (LEFT, None, RIGHT):
        accel = run.accel_for(port)
        err = abs(accel - owed)
        if best_err is None or err < best_err:
            best, best_err, best_accel = port, err, accel
    run.owed = owed - best_accel
    return best


def act(run: Run, port: int) -> None:
    if port == GRAB:
        run.grab()


def apply(run: Run, port: Optional[int]) -> None:
    """For tests and play: events act; others are the next control."""
    if port in EVENTS:
        act(run, port)


def play(yard: Yard, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(yard)
    while run.result is None:
        control = None
        for port in pilot(run):
            if port in EVENTS:
                act(run, port)
            else:
                control = port
        run.step(dt, control)
    return run.result
