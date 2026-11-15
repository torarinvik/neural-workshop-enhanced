# -*- coding: utf-8 -*-
"""Crossroads: run the traffic lights so the town never jams.

Cars come into town along every road and queue at red lights. Each
junction shows green one way at a time; switching it goes through
amber and a moment of all-red so the junction clears. A road whose
queue backs up past the edge of town -- more than a few cars that
cannot even get onto it -- is gridlock, and the shift is lost. From
rung 10 ambulances come through, lights flashing; one held at a red
light too long loses the shift too.

The ladder:

* rungs 1-3: one junction, light traffic;
* rungs 4-6: heavier traffic, lopsided between the roads;
* rungs 7-9: two junctions on one main road;
* rungs 10-12: ambulances;
* rungs 13-15: four junctions in a square;
* rungs 16-19: rush hour -- the busy road changes partway;
* from rung 20: more traffic, more ambulances, a longer shift.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

MOST = 4
PORTS = MOST
EVENTS = tuple(range(MOST))
WORLD_W, WORLD_H = 72.0, 48.0
SPEED = 9.0
ACCEL = 5.0
BRAKE = 9.0
GAP = 5.5               # front to front, queued
STOP_BACK = 4.5         # stop line before a junction's centre
AMBER = 1.6
ALL_RED = 1.2
BACKLOG = 3             # cars waiting off the map before it is gridlock
LANE = 1.6              # offset of a lane from the road's centre line
AMBULANCE_WAIT = 4.0


class Grade(NamedTuple):
    rung: int
    layout: int          # 1, 2 or 4 junctions
    rate: float          # cars a second on a busy road
    lopsided: float      # quiet roads' share of the busy rate
    ambulances: int
    rush: bool
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        layout=1 if r < 7 else 2 if r < 13 else 4,
        rate=(0.16 if r < 4 else 0.22 if r < 7 else 0.2 if r < 13
              else 0.17 if r < 20 else min(0.24, 0.18 + 0.004 * top)),
        lopsided=0.8 if r < 4 else 0.45,
        ambulances=0 if r < 10 else 2 if r < 20 else 3 + top // 4,
        rush=r >= 16,
        seconds=70.0 if r < 20 else 80.0 + top)


class Junction(NamedTuple):
    x: float
    y: float


class Path(NamedTuple):
    """One direction of one road: entry point, direction, length, and
    (distance along, junction index) for each junction crossed."""
    x0: float
    y0: float
    dx: int
    dy: int
    length: float
    crosses: Tuple[Tuple[float, int], ...]
    axis: str            # 'EW' or 'NS'


class Town(NamedTuple):
    level: Grade
    junctions: List[Junction]
    paths: List[Path]
    arrivals: List[Tuple[float, int, bool]]   # (time, path, ambulance)
    start_green: List[str]


def _layout(n: int) -> Tuple[List[Junction], List[Path]]:
    if n == 1:
        xs, ys = [WORLD_W / 2], [WORLD_H / 2]
    elif n == 2:
        xs, ys = [WORLD_W * 0.33, WORLD_W * 0.67], [WORLD_H / 2]
    else:
        xs, ys = [WORLD_W * 0.33, WORLD_W * 0.67], \
            [WORLD_H * 0.32, WORLD_H * 0.68]
    junctions = [Junction(x, y) for y in ys for x in xs]
    paths = []
    for y in ys:
        for d in (1, -1):
            lane_y = y - d * LANE
            x0 = 0.0 if d > 0 else WORLD_W
            crosses = sorted((abs(j.x - x0), k)
                             for k, j in enumerate(junctions) if j.y == y)
            paths.append(Path(x0, lane_y, d, 0, WORLD_W, tuple(crosses),
                              'EW'))
    for x in xs:
        for d in (1, -1):
            lane_x = x + d * LANE
            y0 = 0.0 if d > 0 else WORLD_H
            crosses = sorted((abs(j.y - y0), k)
                             for k, j in enumerate(junctions) if j.x == x)
            paths.append(Path(lane_x, y0, 0, d, WORLD_H, tuple(crosses),
                              'NS'))
    return junctions, paths


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Town:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(20):
        town = _build(level, draw)
        best = best or town
        if play(town)[0] and not play(town, lambda run: [])[0]:
            return town
    return best


def _build(level: Grade, draw: random.Random) -> Town:
    junctions, paths = _layout(level.layout)
    busy_axis = draw.choice(('EW', 'NS'))
    switch_at = draw.uniform(0.35, 0.6) * level.seconds if level.rush \
        else None
    arrivals = []
    for k, p in enumerate(paths):
        t = draw.uniform(0, 3)
        while t < level.seconds:
            axis = busy_axis
            if switch_at is not None and t >= switch_at:
                axis = 'NS' if busy_axis == 'EW' else 'EW'
            rate = level.rate * (1.0 if p.axis == axis else level.lopsided)
            arrivals.append((round(t, 2), k, False))
            t += draw.expovariate(rate) + 0.9
    for _a in range(level.ambulances):
        arrivals.append((round(draw.uniform(8, level.seconds - 12), 2),
                         draw.randrange(len(paths)), True))
    arrivals.sort()
    start = [draw.choice(('EW', 'NS')) for _j in junctions]
    return Town(level, junctions, paths, arrivals, start)


class Car:
    __slots__ = ('path', 's', 'v', 'ambulance', 'waited', 'colour',
                 'born')

    def __init__(self, path: int, ambulance: bool, colour: int,
                 born: float) -> None:
        self.path = path
        self.s = 0.0
        self.v = SPEED * 0.8
        self.ambulance = ambulance
        self.waited = 0.0
        self.colour = colour
        self.born = born


class Light:
    __slots__ = ('green', 'changing', 'since')

    def __init__(self, green: str) -> None:
        self.green = green           # the axis that has (or last had) green
        self.changing: Optional[float] = None   # when the switch began
        self.since = 0.0

    def state(self, axis: str, t: float) -> str:
        """'green', 'amber' or 'red' for *axis* at time *t*."""
        if self.changing is None:
            return 'green' if axis == self.green else 'red'
        into = t - self.changing
        if axis == self.green and into < AMBER:
            return 'amber'
        return 'red'


class Run:
    def __init__(self, town: Town) -> None:
        self.town = town
        self.level = town.level
        self.t = 0.0
        self.cars: List[Car] = []
        self.lights = [Light(g) for g in town.start_green]
        self.backlog: Dict[int, List[Tuple[bool, float]]] = {
            k: [] for k in range(len(town.paths))}
        self.next_arrival = 0
        self.served = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.palette = 0
        self.total_wait = 0.0

    def toggle(self, k: int) -> None:
        if self.result is not None or not 0 <= k < len(self.lights):
            return
        light = self.lights[k]
        if light.changing is None:
            light.changing = self.t

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        town = self.town
        for light in self.lights:
            if light.changing is not None and \
                    self.t - light.changing >= AMBER + ALL_RED:
                light.green = 'NS' if light.green == 'EW' else 'EW'
                light.changing = None
                light.since = self.t
        while self.next_arrival < len(town.arrivals) and \
                town.arrivals[self.next_arrival][0] <= self.t:
            _t, k, amb = town.arrivals[self.next_arrival]
            self.backlog[k].append((amb, self.t))
            self.next_arrival += 1
        # Let waiting cars onto their road if there is room.
        for k, waiting in self.backlog.items():
            if not waiting:
                continue
            last = min((c.s for c in self.cars if c.path == k),
                       default=99.0)
            if last >= GAP:
                amb, born = waiting.pop(0)
                self.palette += 1
                self.cars.append(Car(k, amb, self.palette, born))
            if len(waiting) > BACKLOG:
                self.result = (False, _('Gridlock: traffic backed out of '
                                        'town'))
                return
        # Drive.
        by_path: Dict[int, List[Car]] = {}
        for c in self.cars:
            by_path.setdefault(c.path, []).append(c)
        gone = []
        for k, cars in by_path.items():
            path = town.paths[k]
            cars.sort(key=lambda c: -c.s)
            ahead = None
            for c in cars:
                limit = path.length + 20.0
                if ahead is not None:
                    limit = ahead.s - GAP
                for at, j in path.crosses:
                    stop = at - STOP_BACK
                    if c.s <= stop + 0.05:
                        state = self.lights[j].state(path.axis, self.t)
                        if state != 'green':
                            # Amber: go on if it cannot stop in time.
                            reach = c.v * c.v / (2 * BRAKE)
                            if state == 'red' or stop - c.s > reach:
                                limit = min(limit, stop)
                        break
                room = max(0.0, limit - c.s)
                top = min(SPEED, math.sqrt(2 * BRAKE * room))
                if c.v < top:
                    c.v = min(top, c.v + ACCEL * dt)
                else:
                    c.v = top
                c.s = min(limit if limit > c.s else c.s, c.s + c.v * dt)
                if c.v < 0.5:
                    c.waited += dt
                    self.total_wait += dt
                    if c.ambulance and c.waited > AMBULANCE_WAIT:
                        self.result = (False, _('An ambulance was held up'))
                        return
                else:
                    c.waited = max(0.0, c.waited - dt * 0.5) \
                        if not c.ambulance else c.waited
                if c.s > path.length + 4.0:
                    gone.append(c)
                ahead = c
        for c in gone:
            self.cars.remove(c)
            self.served += 1
        if self.t >= self.level.seconds:
            self.result = (True, _('%d cars through, no jam') % self.served)

    def where(self, c: Car) -> Tuple[float, float]:
        p = self.town.paths[c.path]
        return p.x0 + p.dx * c.s, p.y0 + p.dy * c.s

    def queue(self, path: int) -> int:
        return sum(1 for c in self.cars if c.path == path and c.v < 0.5) \
            + len(self.backlog[path])


# --- the reference controller -------------------------------------------------

def _pressure(run: Run, j: int, axis: str) -> Tuple[float, bool]:
    """How much the roads of *axis* want junction *j*, and whether an
    ambulance is coming that way."""
    town = run.town
    total, urgent = 0.0, False
    for c in run.cars:
        p = town.paths[c.path]
        if p.axis != axis:
            continue
        for at, k in p.crosses:
            if k != j:
                continue
            gap = at - STOP_BACK - c.s
            if -0.5 < gap < 40.0:
                total += 1.0 + c.waited * 0.4
                if c.ambulance and gap < 45.0:
                    urgent = True
            break
    for k, waiting in run.backlog.items():
        p = town.paths[k]
        if p.axis == axis and p.crosses and p.crosses[0][1] == j:
            total += 2.5 * len(waiting)
            if any(a for a, _b in waiting):
                urgent = True
    return total, urgent


def autopilot(run: Run) -> List[int]:
    if run.result is not None:
        return []
    out = []
    for j, light in enumerate(run.lights):
        if light.changing is not None:
            continue
        green = light.green
        red = 'NS' if green == 'EW' else 'EW'
        held = run.t - light.since
        g_p, g_amb = _pressure(run, j, green)
        r_p, r_amb = _pressure(run, j, red)
        if r_amb and not g_amb and held > 1.0:
            out.append(j)
        elif held > 5.0 and r_p > g_p * 1.4 + 1.5 and not g_amb:
            out.append(j)
    return out


def act(run: Run, port: int) -> None:
    run.toggle(port)


def play(town: Town, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(town)
    while run.result is None:
        for port in pilot(run):
            act(run, port)
        run.step(dt)
    return run.result
