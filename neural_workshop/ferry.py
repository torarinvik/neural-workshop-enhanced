# -*- coding: utf-8 -*-
"""Ferry: carry passengers across a river that wants to carry you away.

A small ferry crosses a wide river between piers on the two banks. The
river runs left to right, fastest in midstream and slack at the banks,
so the ferry has to crab across, nose upstream. Barges work up and down
the river in lanes; a ferry that touches one is lost. Dock by coming to
rest inside the lit pier's box; the passengers take a moment to step
aboard or ashore, and then the other bank's pier lights up.

Controls are a throttle and a rudder: forward, astern, turn left, turn
right, and forward while turning either way.

The ladder:

* rungs 1-3: a gentle river, two crossings, no traffic;
* rungs 4-6: one lane of barges;
* rungs 7-9: a stronger river, two lanes;
* rungs 10-12: three lanes and three crossings;
* rungs 13-15: gusts up and down the river;
* rungs 16-19: fog -- barges show only near the ferry;
* from rung 20: faster barges, a stronger river, more crossings.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

AHEAD, ASTERN, LEFT, RIGHT, AHEAD_LEFT, AHEAD_RIGHT = range(6)
PORTS = 6
EVENTS = ()
WORLD_W, WORLD_H = 64.0, 40.0
SOUTH, NORTH = 3.0, 37.0          # the water's edges
THRUST = 2.2                       # m/s^2 at full ahead
DRAG = 0.45
TURN = 55.0                        # degrees a second
TOP = 4.5                          # top speed through the water
HULL = 2.0                         # the ferry's radius, for touching
BARGE_HALF = (5.0, 1.4)            # half length, half beam
FOG = 16.0


class Grade(NamedTuple):
    rung: int
    current: float
    crossings: int
    lanes: int
    barge_speed: float
    gusts: float
    fog: bool
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    crossings = 2 if r < 10 else 3 if r < 20 else min(5, 3 + top // 4)
    return Grade(
        rung=r,
        current=(1.0 if r < 4 else 1.4 if r < 7 else 2.0 if r < 20
                 else min(3.0, 2.2 + 0.08 * top)),
        crossings=crossings,
        lanes=0 if r < 4 else 1 if r < 7 else 2 if r < 10 else 3,
        barge_speed=3.0 if r < 20 else min(5.0, 3.4 + 0.15 * top),
        gusts=0.0 if r < 13 else 0.5 + 0.03 * top,
        fog=r >= 16,
        seconds=40.0 + 45.0 * crossings)


class Barge(NamedTuple):
    lane_y: float
    speed: float           # + downstream, - upstream
    start: float           # x at t = 0
    gap: float             # spacing of barges in the lane


class River(NamedTuple):
    level: Grade
    piers: List[Tuple[float, float]]     # (x, y) dock points, in order
    barges: List[Barge]
    gust_seed: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> River:
    """A river the reference skipper crosses."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(20):
        river = _build(level, draw)
        best = best or river
        if play(river)[0]:
            return river
    return best


def _build(level: Grade, draw: random.Random) -> River:
    piers = []
    for k in range(level.crossings + 1):
        bank_y = SOUTH + 2.2 if k % 2 == 0 else NORTH - 2.2
        piers.append((draw.uniform(12.0, WORLD_W - 16.0), bank_y))
    lanes = {0: [], 1: [20.0], 2: [14.0, 26.0],
             3: [9.5, 20.0, 30.5]}[level.lanes]
    barges = []
    for k, y in enumerate(lanes):
        sign = 1.0 if k % 2 == 0 else -0.7
        barges.append(Barge(y, sign * level.barge_speed * draw.uniform(
            0.85, 1.15), draw.uniform(0, WORLD_W), draw.uniform(44.0, 62.0)))
    return River(level, piers, barges, draw.randrange(1 << 20))


def current_at(level: Grade, y: float) -> float:
    if y <= SOUTH or y >= NORTH:
        return 0.0
    return level.current * math.sin(math.pi * (y - SOUTH) / (NORTH - SOUTH))


# --- the run -------------------------------------------------------------------------

class Run:
    """The ferry and the river in motion."""

    def __init__(self, river: River) -> None:
        self.river = river
        self.level = river.level
        self.t = 0.0
        self.x, self.y = river.piers[0]
        self.heading = 90.0            # degrees; 90 is north
        self.speed = 0.0               # through the water, along heading
        self.leg = 1                   # index of the pier being sailed to
        self.docked_since: Optional[float] = None
        self.result: Optional[Tuple[bool, str]] = None
        self.wake: List[Tuple[float, float, float]] = []
        self.thrusting = 0

    def gust(self, t: Optional[float] = None) -> float:
        if not self.level.gusts:
            return 0.0
        t = self.t if t is None else t
        k = self.river.gust_seed % 11
        return self.level.gusts * math.sin(t * 0.45 + k) * math.sin(
            t * 0.17 + 2 * k)

    def barge_positions(self, t: Optional[float] = None
                        ) -> List[Tuple[float, float, float]]:
        """(x, y, direction) for every barge now on the water."""
        t = self.t if t is None else t
        out = []
        span = WORLD_W + 2 * BARGE_HALF[0] + 8.0
        for b in self.river.barges:
            k = 0
            while k * b.gap < span:
                x = (b.start + k * b.gap + b.speed * t) % span \
                    - BARGE_HALF[0] - 4.0
                out.append((x, b.lane_y, 1.0 if b.speed > 0 else -1.0))
                k += 1
        return out

    def ground_velocity(self) -> Tuple[float, float]:
        h = math.radians(self.heading)
        return (self.speed * math.cos(h) + current_at(self.level, self.y)
                + self.gust(), self.speed * math.sin(h))

    def target(self) -> Tuple[float, float]:
        return self.river.piers[self.leg]

    def step(self, dt: float, control: Optional[int]) -> None:
        if self.result is not None:
            return
        self.t += dt
        ahead = control in (AHEAD, AHEAD_LEFT, AHEAD_RIGHT)
        self.thrusting = 1 if ahead else -1 if control == ASTERN else 0
        push = THRUST if ahead else -THRUST * 0.7 if control == ASTERN \
            else 0.0
        self.speed += (push - DRAG * self.speed) * dt
        self.speed = max(-2.0, min(TOP, self.speed))
        if control in (LEFT, AHEAD_LEFT):
            self.heading += TURN * dt
        elif control in (RIGHT, AHEAD_RIGHT):
            self.heading -= TURN * dt
        self.heading %= 360.0
        vx, vy = self.ground_velocity()
        self.x += vx * dt
        self.y += vy * dt
        if self.wake and math.hypot(self.x - self.wake[-1][0],
                                    self.y - self.wake[-1][1]) > 0.8 \
                or not self.wake:
            self.wake.append((self.x, self.y, self.t))
            del self.wake[:-40]
        # Banks: a soft stop, or a wreck if hit hard.
        low, high = SOUTH + 1.2, NORTH - 1.2
        if self.y < low or self.y > high:
            if abs(vy) > 1.6:
                self.result = (False, _('The ferry ran hard aground'))
                return
            self.y = max(low, min(high, self.y))
            h = math.radians(self.heading)
            self.speed *= max(0.0, 1.0 - 4.0 * dt)
            del h
        if self.x < 1.0 or self.x > WORLD_W - 1.0:
            self.result = (False, _('Swept out of the harbour'))
            return
        for bx, by, _d in self.barge_positions():
            dx = max(0.0, abs(self.x - bx) - BARGE_HALF[0])
            dy = max(0.0, abs(self.y - by) - BARGE_HALF[1])
            if math.hypot(dx, dy) < HULL * 0.8:
                self.result = (False, _('The ferry struck a barge'))
                return
        self._dock()
        if self.result is None and self.t >= self.level.seconds:
            self.result = (False, _('Out of time'))

    def at_pier(self) -> bool:
        tx, ty = self.target()
        vx, vy = self.ground_velocity()
        return (abs(self.x - tx) < 2.2 and abs(self.y - ty) < 1.6
                and math.hypot(vx, vy) < 0.9)

    def _dock(self) -> None:
        if self.at_pier():
            if self.docked_since is None:
                self.docked_since = self.t
            elif self.t - self.docked_since >= 2.0:
                self.docked_since = None
                if self.leg == len(self.river.piers) - 1:
                    self.result = (True, _('%d crossings in %.0f s') % (
                        self.leg, self.t))
                else:
                    self.leg += 1
        else:
            self.docked_since = None


# --- the reference skipper --------------------------------------------------------------

REACH = BARGE_HALF[1] + HULL + 1.4     # a lane's edge, for waiting at
DASH = 3.4                              # crossing speed through a lane


def _lane_clear(run: Run, lane: float, seconds: float) -> bool:
    """Whether no barge in *lane* comes near the ferry's x for a while."""
    t = 0.0
    while t <= seconds:
        for bx, by, _d in run.barge_positions(run.t + t):
            if abs(by - lane) < 0.1 and \
                    abs(bx - run.x) < BARGE_HALF[0] + HULL + 2.0:
                return False
        t += 0.2
    return True


def autopilot(run: Run) -> List[int]:
    """Lane by lane: wait at a lane's edge until it is clear for long
    enough to cross, dash over it, and crab on to the pier."""
    if run.result is not None:
        return []
    tx, ty = run.target()
    way = 1.0 if ty > run.y else -1.0
    lanes = sorted((b.lane_y for b in run.river.barges),
                   key=lambda y: (y - run.y) * way)
    lanes = [y for y in lanes if (y + way * REACH - run.y) * way > 0
             and (ty - y) * way > 0]
    vx = max(-1.5, min(1.5, (tx - run.x) * 0.3))
    if lanes:
        lane = lanes[0]
        gate = lane - way * REACH
        committed = getattr(run, 'committed', None) == (lane, way) and \
            abs(run.y - lane) < REACH + 0.3
        if committed:
            want = (vx * 0.3, way * DASH)      # in the lane: keep going
        elif (gate - run.y) * way > 0.5:
            # Not there yet: make for the gate, slow enough to stop at it.
            gap = abs(gate - run.y)
            vy = way * min(3.0, 0.3 + math.sqrt(2 * 0.7 * gap))
            want = (vx, vy)
        else:
            # At the gate: go only if the lane stays clear long enough.
            cross = (2 * REACH + abs(gate - run.y)) / DASH + 2.5
            if _lane_clear(run, lane, cross):
                run.committed = (lane, way)
                want = (vx * 0.3, way * DASH)
            else:
                want = (vx * 0.5, (gate - run.y) * 1.0)
    else:
        dx, dy = tx - run.x, ty - run.y
        dist = math.hypot(dx, dy)
        cruise = min(3.2, 0.25 + dist * 0.45)
        want = (dx / dist * cruise, dy / dist * cruise) if dist > 0.05 \
            else (0.0, 0.0)
    # Never run at a bank faster than the ferry can stop.
    room = (NORTH - 1.2 - run.y) if want[1] > 0 else (run.y - SOUTH - 1.2)
    limit = max(0.4, room * 0.9)
    if abs(want[1]) > limit:
        want = (want[0], math.copysign(limit, want[1]))
    # Through the water: the ground velocity wanted, less the river.
    wx = want[0] - current_at(run.level, run.y) - run.gust()
    wy = want[1]
    need = math.hypot(wx, wy)
    if need < 0.15:
        head = run.heading
    else:
        head = math.degrees(math.atan2(wy, wx))
    err = (head - run.heading + 540.0) % 360.0 - 180.0
    along = need * math.cos(math.radians(err))
    turn = LEFT if err > 6 else RIGHT if err < -6 else None
    if run.speed < along - 0.15 and abs(err) < 70:
        if turn == LEFT:
            return [AHEAD_LEFT]
        if turn == RIGHT:
            return [AHEAD_RIGHT]
        return [AHEAD]
    if run.speed > along + 0.5 and abs(err) < 100:
        return [ASTERN]
    return [turn] if turn is not None else []


def act(run: Run, port: int) -> None:
    pass


def play(river: River, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(river)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
