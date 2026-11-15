# -*- coding: utf-8 -*-
"""Time It: press when the hidden ball reaches the mark.

A ball comes rolling (or flying) and goes behind a screen; a mark on the
screen shows a spot it will pass. Press at the moment it is there. The
ball cannot be seen when it matters, so its motion has to be carried on
in the head -- its speed, its slowing, its bounce, its fall -- from the
stretch where it could be seen. After the press, the screen lifts and
shows where the ball really was.

The ladder:

* rungs 1-3: a steady roll, a short screen, a wide window;
* rungs 4-6: a longer screen, a narrower window;
* rungs 7-9: the ball slows as it rolls -- friction, steady and visible;
* rungs 10-12: it bounces off a wall behind the screen and comes back;
* rungs 13-15: it is thrown and falls in an arc; the mark is where it
  lands;
* rungs 16-19: any of these, faster, longer hidden;
* from rung 20: tighter windows every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

PRESS = 0
PORTS = 1
EVENTS = (PRESS,)
W, H = 100.0, 50.0
GROUND = 6.0
G = 40.0                     # units / s^2, for the throw


class Grade(NamedTuple):
    rung: int
    kinds: Tuple[str, ...]   # 'roll', 'slow', 'bounce', 'throw'
    hidden: Tuple[float, float]   # seconds the ball is hidden before the mark
    window: float            # +- seconds
    speed: Tuple[float, float]


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    kinds = (('roll',) if r < 7 else ('slow',) if r < 10 else ('bounce',)
             if r < 13 else ('throw',) if r < 16 else
             ('roll', 'slow', 'bounce', 'throw'))
    return Grade(
        rung=r,
        kinds=kinds,
        hidden=((0.5, 0.8) if r < 4 else (0.9, 1.4) if r < 16
                else (1.2, 1.9)),
        window=(0.12 if r < 4 else 0.09 if r < 16 else 0.08 if r < 20
                else max(0.05, 0.075 - 0.003 * top)),
        speed=((22, 28) if r < 16 else (28, 40)))


class Shot(NamedTuple):
    level: Grade
    kind: str
    x0: float                # where the ball starts
    v: float                 # its speed (or across speed, thrown)
    decel: float             # slowing, units / s^2
    wall: float              # where it bounces, if it does
    vy: float                # upward speed, thrown
    screen: Tuple[float, float]   # the screen's left and right
    mark: float              # the mark's x
    when: float              # when the ball is at the mark


def where(shot: Shot, t: float) -> Tuple[float, float]:
    """The ball's place at time *t*."""
    if shot.kind == 'throw':
        return (shot.x0 + shot.v * t,
                max(GROUND, GROUND + shot.vy * t - 0.5 * G * t * t))
    if shot.kind == 'slow':
        stop = shot.v / shot.decel
        t = min(t, stop)
        return shot.x0 + shot.v * t - 0.5 * shot.decel * t * t, GROUND
    x = shot.x0 + shot.v * t
    if shot.kind == 'bounce' and x > shot.wall:
        x = 2 * shot.wall - x
    return x, GROUND


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Shot:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(500):
        kind = draw.choice(level.kinds)
        v = draw.uniform(*level.speed)
        hidden = draw.uniform(*level.hidden)
        seen = draw.uniform(1.4, 2.2)      # seconds in view first
        x0 = 4.0
        if kind == 'roll':
            when = seen + hidden
            left = x0 + v * seen
            mark = x0 + v * when
            shot = Shot(level, kind, x0, v, 0.0, 0.0, 0.0,
                        (left, min(W - 2, mark + draw.uniform(6, 14))),
                        mark, when)
        elif kind == 'slow':
            decel = draw.uniform(0.25, 0.4) * v / (seen + hidden)
            when = seen + hidden
            stop = v / decel
            if stop < when + 0.4:
                continue
            left = where(Shot(level, kind, x0, v, decel, 0, 0, (0, 0), 0, 0),
                         seen)[0]
            mark = where(Shot(level, kind, x0, v, decel, 0, 0, (0, 0), 0, 0),
                         when)[0]
            shot = Shot(level, kind, x0, v, decel, 0.0, 0.0,
                        (left, min(W - 2, mark + draw.uniform(6, 12))),
                        mark, when)
        elif kind == 'bounce':
            left = x0 + v * seen
            wall = left + v * hidden * draw.uniform(0.55, 0.8)
            when = seen + hidden
            mark = 2 * wall - (x0 + v * when)
            if mark < left + 4 or wall > W - 3:
                continue
            shot = Shot(level, kind, x0, v, 0.0, wall, 0.0,
                        (left, min(W - 1, wall + 3)), mark, when)
        else:
            flight = seen + hidden
            vx = draw.uniform(18, 24)
            vy = 0.5 * G * flight
            mark = x0 + vx * flight
            if mark > W - 6 or GROUND + vy * vy / (2 * G) > H - 3:
                continue
            left = x0 + vx * seen
            shot = Shot(level, kind, x0, vx, 0.0, 0.0, vy,
                        (left, min(W - 1, mark + draw.uniform(5, 10))),
                        mark, flight)
        if shot.screen[1] - shot.screen[0] < 8 or shot.mark > W - 3:
            continue
        return shot
    raise RuntimeError('no Time It shot for rung %d' % rung)


class Run:
    def __init__(self, shot: Shot) -> None:
        self.shot = shot
        self.level = shot.level
        self.t = 0.0
        self.pressed: Optional[float] = None
        self.result: Optional[Tuple[bool, str]] = None

    def press(self) -> None:
        if self.result is not None or self.pressed is not None:
            return
        self.pressed = self.t
        off = self.t - self.shot.when
        if abs(off) <= self.level.window:
            self.result = (True, _('On the mark -- %+d ms') %
                           round(off * 1000))
        else:
            self.result = (False, _('%d ms %s') % (
                abs(round(off * 1000)), _('early') if off < 0 else _('late')))

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t > self.shot.when + self.level.window + 0.6:
            self.result = (False, _('No press -- the ball went by'))


def act(run: Run, port: int) -> None:
    if port == PRESS:
        run.press()


def autopilot(run: Run) -> List[int]:
    if run.result is None and \
            run.t <= run.shot.when < run.t + 1 / 60.0 + 1e-9:
        return [PRESS]
    return []


def play(shot: Shot, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(shot)
    while run.result is None:
        for port in pilot(run):
            act(run, port)
        run.step(dt)
    return run.result
