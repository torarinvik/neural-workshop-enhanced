# -*- coding: utf-8 -*-
"""Balance: carry a pole upright on a cart from flag to flag.

A cart runs on a straight track with a pole hinged on top. Push the
cart left or right; the pole leans the other way and falls unless the
cart gets back under it. To move right you must first let the pole
lean right -- which means nudging left. Each flag is collected by
standing the cart still under it, pole up, for a second.

The ladder:

* rungs 1-3: a long, slow pole, two flags close together;
* rungs 4-6: a shorter pole, three flags;
* rungs 7-9: flags far apart;
* rungs 10-12: gusts push the pole;
* rungs 13-15: a short, quick pole;
* rungs 16-19: the pole's length changes partway through, unannounced;
* from rung 20: shorter still, stronger gusts, more flags.

Fails: the pole past 35 degrees, the cart into a buffer stop, the
time running out.

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
TRACK = 30.0
G = 9.8
PUSH = 12.0           # cart acceleration under a push
ROLL = 0.6            # cart slowing with no push
FALLEN = math.radians(35.0)
HOLD = 1.0            # seconds still at a flag


class Grade(NamedTuple):
    rung: int
    length: float
    flags: int
    spread: float
    gusts: float
    changes: bool
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    flags = 2 if r < 4 else 3 if r < 20 else min(6, 4 + top // 4)
    return Grade(
        rung=r,
        length=(3.0 if r < 4 else 2.0 if r < 13 else 1.4 if r < 20
                else max(0.9, 1.2 - 0.03 * top)),
        flags=flags,
        spread=6.0 if r < 7 else 14.0,
        gusts=0.0 if r < 10 else (0.6 if r < 20 else 0.8 + 0.04 * top),
        changes=r >= 16,
        seconds=20.0 + 9.0 * flags)


class Course(NamedTuple):
    level: Grade
    flags: List[float]
    lengths: List[Tuple[float, float]]    # (from time, pole length)
    gust_seed: int


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Course:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(20):
        course = _build(level, draw)
        best = best or course
        if play(course)[0]:
            return course
    return best


def _build(level: Grade, draw: random.Random) -> Course:
    flags = []
    x = TRACK / 2
    for _k in range(level.flags):
        for _try in range(50):
            nx = x + draw.choice((-1, 1)) * draw.uniform(
                level.spread * 0.6, level.spread)
            if 3.0 <= nx <= TRACK - 3.0:
                break
        else:
            nx = TRACK - x
        flags.append(round(nx, 2))
        x = nx
    lengths = [(0.0, level.length)]
    if level.changes:
        lengths.append((draw.uniform(8.0, 14.0),
                        level.length * draw.choice((0.6, 1.6))))
    return Course(level, flags, lengths, draw.randrange(1 << 20))


class Run:
    def __init__(self, course: Course) -> None:
        self.course = course
        self.level = course.level
        self.t = 0.0
        self.x = TRACK / 2
        self.v = 0.0
        self.theta = 0.02
        self.omega = 0.0
        self.flag = 0
        self.still = 0.0
        self.result: Optional[Tuple[bool, str]] = None
        self.pushing = 0

    def length(self, t: Optional[float] = None) -> float:
        t = self.t if t is None else t
        out = self.course.lengths[0][1]
        for when, l in self.course.lengths:
            if t >= when:
                out = l
        return out

    def gust(self, t: Optional[float] = None) -> float:
        if not self.level.gusts:
            return 0.0
        t = self.t if t is None else t
        k = self.course.gust_seed % 17
        return self.level.gusts * math.sin(t * 0.8 + k) * \
            math.sin(t * 0.31 + 2 * k)

    def accel_for(self, control: Optional[int]) -> float:
        if control == LEFT:
            return -PUSH
        if control == RIGHT:
            return PUSH
        if abs(self.v) < 1e-9:
            return 0.0
        return -math.copysign(ROLL, self.v)

    def step(self, dt: float, control: Optional[int]) -> None:
        if self.result is not None:
            return
        self.t += dt
        a = self.accel_for(control)
        self.pushing = 1 if control == RIGHT else -1 if control == LEFT \
            else 0
        before = self.v
        self.v += a * dt
        if control is None and before * self.v < 0:
            self.v = 0.0
        self.x += self.v * dt
        l = self.length()
        alpha = ((G * math.sin(self.theta) - a * math.cos(self.theta)
                  + self.gust()) / l - 0.1 * self.omega)
        self.omega += alpha * dt
        self.theta += self.omega * dt
        if abs(self.theta) > FALLEN:
            self.result = (False, _('The pole fell'))
            return
        if self.x < 0.6 or self.x > TRACK - 0.6:
            self.result = (False, _('The cart hit the buffers'))
            return
        target = self.course.flags[self.flag]
        if abs(self.x - target) < 0.8 and abs(self.v) < 1.0 and \
                abs(self.theta) < math.radians(12):
            self.still += dt
            if self.still >= HOLD:
                self.still = 0.0
                self.flag += 1
                if self.flag == len(self.course.flags):
                    self.result = (True, _('Every flag, in %.0f s') % self.t)
                    return
        else:
            self.still = 0.0
        if self.t >= self.level.seconds:
            self.result = (False, _('Out of time'))


# --- the reference balancer -----------------------------------------------------

#: Regulator gains by pole length, worked out offline (linear quadratic,
#: cart acceleration as the input): a = k0 (x - flag) + k1 v + k2 theta
#: + k3 omega.
GAINS = ((0.8, (4.198, 7.861, 65.168, 18.202)),
         (1.0, (4.226, 8.13, 69.53, 21.482)),
         (1.4, (4.26, 8.598, 77.785, 28.181)),
         (2.0, (4.286, 9.203, 89.453, 38.594)),
         (3.0, (4.308, 10.066, 107.761, 56.887)),
         (4.0, (4.32, 10.818, 125.173, 76.261)))


def _gains(l: float) -> Tuple[float, ...]:
    if l <= GAINS[0][0]:
        return GAINS[0][1]
    for (l0, k0), (l1, k1) in zip(GAINS, GAINS[1:]):
        if l <= l1:
            f = (l - l0) / (l1 - l0)
            return tuple(a + (b - a) * f for a, b in zip(k0, k1))
    return GAINS[-1][1]


def autopilot(run: Run) -> List[int]:
    """The regulator's acceleration, as on-off pushes whose error
    carries over to the next steps. It knows the pole's length only by
    watching how the pole moves -- here, simply, by being told."""
    if run.result is not None:
        return []
    k = _gains(run.length())
    target = run.course.flags[run.flag]
    err = max(-3.0, min(3.0, run.x - target))
    lean = run.gust() / G
    wanted = (k[0] * err + k[1] * run.v + k[2] * (run.theta + lean)
              + k[3] * run.omega)
    owed = getattr(run, 'owed', 0.0) * 0.9 + wanted
    best, best_err, best_a = None, None, 0.0
    for port in (LEFT, None, RIGHT):
        a = run.accel_for(port)
        e = abs(a - owed)
        if best_err is None or e < best_err:
            best, best_err, best_a = port, e, a
    run.owed = owed - best_a
    return [] if best is None else [best]


def act(run: Run, port: int) -> None:
    pass


def play(course: Course, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(course)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
