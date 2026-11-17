# -*- coding: utf-8 -*-
"""Glove: catch the pitches while the camera keeps cutting away.

A pitcher throws ball after ball toward the plate, and the glove waits
in front of the catcher's mask. Move the glove into the ball's path:
it has to meet the ball as it reaches the plate. The camera does not
hold still. It cuts without warning between angles -- behind the
catcher, from the side, from above, from down low -- and every cut
turns the way the glove moves on the screen with it.

* rung 1: one camera, behind the catcher; slow, high lobs; a big
  glove, and one miss allowed;
* rungs 2-3: a new angle for every pitch, never during one; faster;
* rungs 4-6: cuts during the flight too, about once a second;
* rungs 7-9: curveballs that bend late; cuts more often;
* rungs 10-12: views from overhead and from the ground join in;
* rungs 13 and up: the cuts come faster and faster, the pitches
  quicken and the glove shrinks, without end.

For the agent boundary: ports 0-3 move the glove up, down, left and
right on the screen as the camera now shows it, for the step they are
sent in.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

UP, DOWN, LEFT, RIGHT = range(4)
PORTS = 4
EVENTS = ()
MOUND = 18.0                   # the release, metres from the plate
RELEASE = (0.0, 1.8)
GLOVE_SPEED = 2.6              # metres a second, through the ports
BOX = (-1.0, 1.0, 0.25, 2.1)   # where the glove can go: x, x, y, y
REST = (0.0, 1.15)
BALL = 0.037
PATCHES = ('wood', 'bell', 'growl')

# the views: eye, the point looked at
VIEWS = (((0.0, 1.6, -5.0), (0.0, 1.6, 9.0)),        # behind the catcher
         ((1.2, 2.6, 23.0), (0.0, 1.1, 0.0)),        # behind the pitcher
         ((-7.0, 1.6, 4.0), (0.0, 1.1, 1.0)),        # first base side
         ((6.0, 2.2, -1.5), (0.0, 1.1, 2.0)),        # third base, behind
         ((-2.5, 0.25, -2.0), (0.0, 1.3, 1.5)),      # down low
         ((0.5, 8.5, -3.5), (0.0, 0.6, 2.0)),        # overhead, steeply
         ((4.0, 5.0, 10.0), (0.0, 1.0, 0.0)))        # high, from the side


class Grade(NamedTuple):
    rung: int
    pitches: int
    misses: int
    speed: float
    curve: float               # how hard the spin bends
    cut: float                 # mean seconds between cuts in flight, or 0
    per_pitch: bool            # a new view at each pitch
    views: int                 # how many of VIEWS are used
    glove: float               # the catching radius
    spread: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, 4, 1, 13.5, 0.0, 0.0, False, 1, 0.24, 0.55)
    if r < 4:
        return Grade(r, 5, 1, 15.5 + 2 * (r - 2), 0.0, 0.0, True, 3, 0.22,
                     0.6)
    if r < 7:
        return Grade(r, 5, 0, 19.0 + 1.5 * (r - 4), 0.0, 1.2 - 0.1 * (r - 4),
                     True, 4, 0.2, 0.6)
    if r < 10:
        return Grade(r, 5, 0, 23.0, 0.6 + 0.2 * (r - 7), 0.8 - 0.05 * (r - 7),
                     True, 5, 0.19, 0.6)
    if r < 13:
        return Grade(r, 6, 0, 25.0, 1.0, 0.6 - 0.05 * (r - 10), True, 7,
                     0.18, 0.55)
    return Grade(r, 6, 0, min(40.0, 26.0 + 0.7 * (r - 13)), 1.2,
                 max(0.1, 0.45 * 0.9 ** (r - 13)), True, 7,
                 max(0.12, 0.17 * 0.97 ** (r - 13)), 0.5)


class Pitch(NamedTuple):
    at: float                       # released
    path: Tuple[Tuple[float, float, float, float], ...]   # t, x, y, z
    cross: Tuple[float, float, float]                     # x, y, t


class Game(NamedTuple):
    level: Grade
    pitches: Tuple[Pitch, ...]
    cuts: Tuple[Tuple[float, int], ...]    # from this time, this view
    seconds: float


def throw(level: Grade, aim: Tuple[float, float], spin: Tuple[float, float],
          at: float) -> Pitch:
    """A pitch from the mound to *aim* on the plate, bent by *spin*."""
    v = level.speed
    x, y, z = RELEASE[0], RELEASE[1], MOUND
    t_fly = MOUND / v
    # aim so that gravity and the spin's bend bring it onto *aim*
    sx, sy = spin
    vx = (aim[0] - x) / t_fly - 0.5 * sx * t_fly
    vy = (aim[1] - y) / t_fly + 0.5 * (9.81 - sy) * t_fly
    vz = -v
    path = [(0.0, x, y, z)]
    t, dt = 0.0, 1 / 240.0
    while z > 0:
        vx += sx * dt
        vy += (sy - 9.81) * dt
        x, y, z = x + vx * dt, y + vy * dt, z + vz * dt
        t += dt
        path.append((t, x, y, z))
    _t0, ax, ay, az = path[-2]
    s = az / (az - z)
    cx, cy = ax + (x - ax) * s, ay + (y - ay) * s
    return Pitch(at, tuple(path), (cx, cy, t - dt * (1 - s)))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Game:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(200):
        pitches = []
        at = 2.0
        last = REST
        for k in range(level.pitches):
            for _j in range(50):
                aim = (REST[0] + draw.uniform(-1, 1) * level.spread,
                       REST[1] + draw.uniform(-1, 1) * level.spread)
                if math.hypot(aim[0] - REST[0], aim[1] - REST[1]) > \
                        level.glove * 1.6 and math.hypot(
                            aim[0] - last[0], aim[1] - last[1]) > \
                        level.glove * 1.6:
                    break
            a = draw.uniform(0, 2 * math.pi)
            bend = level.curve * level.speed ** 2 / MOUND * 0.15
            spin = (bend * math.cos(a), bend * math.sin(a))
            p = throw(level, aim, spin, at)
            pitches.append(p)
            last = aim
            at += p.cross[2] + draw.uniform(1.6, 2.4)
        seconds = at
        cuts = [(0.0, 0)]
        view = 0
        if level.views > 1:
            view = draw.randrange(level.views)
            cuts = [(0.0, view)]
            times = []
            if level.per_pitch:
                times += [p.at - 0.8 for p in pitches[1:]]
            if level.cut:
                t = 0.0
                while t < seconds:
                    t += draw.expovariate(1.0 / level.cut) + 0.08
                    times.append(t)
            for t in sorted(times):
                nv = draw.randrange(level.views - 1)
                view = nv if nv < view else nv + 1
                cuts.append((t, view))
        g = Game(level, tuple(pitches), tuple(cuts), seconds)
        if play(g)[0] and not play(g, lambda run: [])[0]:
            return g
    raise RuntimeError('glove: no game for rung %d' % rung)


def _project(view: int, p):
    """Where a point lands on the screen, up to scale: the same pinhole
    the screen draws with."""
    eye, look = VIEWS[view]
    f = [l - e for l, e in zip(look, eye)]
    n = math.sqrt(sum(c * c for c in f))
    f = [c / n for c in f]
    up = (0.0, 1.0, 0.0) if abs(f[1]) < 0.999 else (0.0, 0.0, 1.0)
    r = (up[1] * f[2] - up[2] * f[1], up[2] * f[0] - up[0] * f[2],
         up[0] * f[1] - up[1] * f[0])
    rn = math.sqrt(sum(c * c for c in r))
    r = [c / rn for c in r]
    u = (f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2],
         f[0] * r[1] - f[1] * r[0])
    d = [q - e for q, e in zip(p, eye)]
    depth = max(1e-3, sum(a * b for a, b in zip(d, f)))
    # the screen's right is the lens's left: x runs the other way
    return (-sum(a * b for a, b in zip(d, r)) / depth,
            sum(a * b for a, b in zip(d, u)) / depth)


def axes(view: int, at: Tuple[float, float] = REST):
    """The ways across the plate's plane that move the glove right and
    up on the screen as the camera shows it, as seen at *at*: each the
    direction that moves the picture fastest that way. A view that
    barely sees a direction still gives it, unit length."""
    e = 0.01
    x, y = at
    p0 = _project(view, (x, y, 0.0))
    px = _project(view, (x + e, y, 0.0))
    py = _project(view, (x, y + e, 0.0))
    j = ((px[0] - p0[0]) / e, (py[0] - p0[0]) / e,
         (px[1] - p0[1]) / e, (py[1] - p0[1]) / e)
    rn = math.hypot(j[0], j[1]) or 1e-9
    un = math.hypot(j[2], j[3]) or 1e-9
    return (j[0] / rn, j[1] / rn), (j[2] / un, j[3] / un)


class Run(object):
    def __init__(self, g: Game) -> None:
        self.g = g
        self.level = g.level
        self.t = 0.0
        self.glove = list(REST)
        self.next = 0                    # the pitch next to reach the plate
        self.caught = 0
        self.missed = 0
        self.flash: Optional[Tuple[float, bool]] = None
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = g.seconds

    def view(self) -> int:
        v = 0
        for t, k in self.g.cuts:
            if t > self.t:
                break
            v = k
        return v

    def ball(self):
        """The ball in flight, or None."""
        for p in self.g.pitches:
            dt = self.t - p.at
            if 0 <= dt <= p.cross[2]:
                i = min(len(p.path) - 1, int(dt * 240))
                return p.path[i][1:]
        return None

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def move(self, dx: float, dy: float) -> None:
        self.glove[0] = max(BOX[0], min(BOX[1], self.glove[0] + dx))
        self.glove[1] = max(BOX[2], min(BOX[3], self.glove[1] + dy))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if isinstance(control, int) and 0 <= control < PORTS:
            right, up = axes(self.view(), tuple(self.glove))
            d = {UP: up, DOWN: (-up[0], -up[1]), RIGHT: right,
                 LEFT: (-right[0], -right[1])}[control]
            self.move(d[0] * GLOVE_SPEED * dt, d[1] * GLOVE_SPEED * dt)
        while self.next < len(self.g.pitches):
            p = self.g.pitches[self.next]
            if self.t < p.at + p.cross[2]:
                break
            self.next += 1
            got = math.hypot(p.cross[0] - self.glove[0],
                             p.cross[1] - self.glove[1]) <= self.level.glove
            self.flash = (self.t, got)
            if got:
                self.caught += 1
                self._note(0.12, 220.0, 0, 0.6)
            else:
                self.missed += 1
                self._note(0.3, 110.0, 2, 0.4)
                if self.missed > self.level.misses:
                    self.result = (False, _('Missed %d') % self.missed)
                    return
        if self.next >= len(self.g.pitches):
            self.result = (True, _('Caught %d of %d') % (
                self.caught, len(self.g.pitches)))


def act(run: Run, port: int) -> None:
    pass


def autopilot(run: Run) -> List[int]:
    """Knows where each pitch will cross from the moment it leaves the
    hand; until then waits at the middle. Moves the glove with whichever
    screen direction best closes the gap under the camera as it is."""
    if run.result is not None or run.next >= len(run.g.pitches):
        return []
    p = run.g.pitches[run.next]
    want = p.cross[:2] if run.t >= p.at else REST
    ex, ey = want[0] - run.glove[0], want[1] - run.glove[1]
    gap = math.hypot(ex, ey)
    if gap < GLOVE_SPEED / 30.0 * 0.6:
        return []
    right, up = axes(run.view(), tuple(run.glove))
    best, port = 0.0, None
    for q, d in ((UP, up), (DOWN, (-up[0], -up[1])), (RIGHT, right),
                 (LEFT, (-right[0], -right[1]))):
        gain = (d[0] * ex + d[1] * ey) / gap
        if gain > best:
            best, port = gain, q
    return [] if port is None or best < 0.2 else [port]


def play(g: Game, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(g)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
