# -*- coding: utf-8 -*-
"""Glider: hold to climb, let go to sink, and thread the gaps.

A glider flies steadily on through a canyon; walls come at it with a
gap in each. Holding lifts it, letting go lets it sink, and it carries
its speed up or down, so it has to be eased, not jerked. Pass every wall
without touching rock, roof or floor.

The ladder:

* rungs 1-3: wide gaps, slow walls, far apart;
* rungs 4-6: narrower gaps, closer walls;
* rungs 7-9: faster;
* rungs 10-12: gaps that slide up and down;
* rungs 13-15: gusts of wind push the glider;
* rungs 16-19: a heavier glider, slower to answer;
* from rung 20: narrower, faster, gustier every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

UP = 0
PORTS = 1
EVENTS = ()
W, H = 100.0, 60.0
X = 22.0                       # where the glider flies
SIZE = 1.6                     # its half height, for touching
WALL = 6.0                     # a wall's thickness


class Grade(NamedTuple):
    rung: int
    gap: float
    speed: float               # walls' speed, units / s
    spacing: float             # between walls
    walls: int
    slide: float               # how far gaps slide, units
    gust: float                # wind strength
    lift: float                # upward acceleration when held
    sink: float                # downward acceleration when not
    damp: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        gap=(26.0 if r < 4 else 20.0 if r < 7 else 18.0 if r < 20
             else max(12.0, 17.0 - 0.4 * top)),
        speed=(18.0 if r < 7 else 26.0 if r < 20 else min(40.0, 27 + top)),
        spacing=(42.0 if r < 4 else 34.0),
        walls=6 if r < 7 else 8 if r < 20 else 10,
        slide=0.0 if r < 10 else 7.0,
        gust=(0.0 if r < 13 else 14.0 + (r - 13) * 0.5 if r < 20
              else 18.0 + top),
        lift=70.0 if r < 16 else 52.0,
        sink=45.0 if r < 16 else 34.0,
        damp=1.6 if r < 16 else 1.0)


class Course(NamedTuple):
    level: Grade
    walls: List[Tuple[float, float, float]]   # (x at t=0, gap centre, phase)
    gust_seed: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Course:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        walls, x, c = [], W + 10, H / 2
        for _k in range(level.walls):
            c = max(level.gap / 2 + level.slide + 4,
                    min(H - level.gap / 2 - level.slide - 4,
                        c + draw.uniform(-16, 16)))
            walls.append((x, c, draw.uniform(0, 2 * math.pi)))
            x += level.spacing * draw.uniform(0.9, 1.15)
        course = Course(level, walls, draw.randrange(1 << 20))
        best = best or course
        if play(course)[0]:
            return course
    return best


class Run:
    def __init__(self, course: Course) -> None:
        self.course = course
        self.level = course.level
        self.t = 0.0
        self.y = H / 2
        self.vy = 0.0
        self.lifting = False
        self.passed = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.trail: List[Tuple[float, float]] = []

    def gust(self, t: Optional[float] = None) -> float:
        if not self.level.gust:
            return 0.0
        t = self.t if t is None else t
        k = self.course.gust_seed % 97
        return self.level.gust * (math.sin(t * 0.9 + k) * 0.6 +
                                  math.sin(t * 2.3 + k * 0.7) * 0.4)

    def wall(self, i: int, t: Optional[float] = None
             ) -> Tuple[float, float]:
        """Wall *i*'s x and its gap's centre at time *t*."""
        t = self.t if t is None else t
        x0, c, ph = self.course.walls[i]
        return (x0 - self.level.speed * t,
                c + self.level.slide * math.sin(t * 1.3 + ph))

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        level = self.level
        self.lifting = control == UP
        acc = (level.lift if self.lifting else -level.sink) + self.gust() \
            - level.damp * self.vy
        self.vy += acc * dt
        self.y += self.vy * dt
        if int(self.t * 20) != int((self.t - dt) * 20):
            self.trail.append((self.t, self.y))
            self.trail = self.trail[-24:]
        if self.y - SIZE < 0 or self.y + SIZE > H:
            self.result = (False, _('Hit the canyon %s') % (
                _('floor') if self.y < H / 2 else _('roof')))
            return
        passed = 0
        for i in range(len(self.course.walls)):
            x, c = self.wall(i)
            if x + WALL / 2 < X - SIZE:
                passed += 1
            elif abs(x - X) < WALL / 2 + SIZE:
                if abs(self.y - c) > level.gap / 2 - SIZE:
                    self.result = (False, _('Hit wall %d') % (i + 1))
                    return
        self.passed = passed
        if passed == len(self.course.walls):
            self.result = (True, _('Through all %d walls') % passed)


def act(run: Run, port: int) -> None:
    pass


def autopilot(run: Run) -> List[int]:
    """Aim at the next gap's centre, as it will be when the glider gets
    there; lift if the glider, coasting, would end up below it."""
    level = run.level
    target = run.y
    for i in range(len(run.course.walls)):
        x, _c = run.wall(i)
        if x + WALL / 2 >= X - SIZE:
            eta = max(0.0, (x - X) / level.speed)
            target = run.wall(i, run.t + min(eta, 0.3))[1]
            break
    # Where the glider would be in a moment either way.
    look = 0.25
    sink_y = run.y + run.vy * look - 0.5 * level.sink * look * look
    return [UP] if sink_y < target else []


def play(course: Course, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(course)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
