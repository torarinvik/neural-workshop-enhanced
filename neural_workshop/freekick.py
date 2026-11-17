# -*- coding: utf-8 -*-
"""Free Kick: bend the ball into the lit part of the goal.

The ball sits on the grass; ahead are the goal, a ring lit on the goal
mouth, and from the fourth rung a wall of defenders and a keeper. Set
the kick -- its direction, how high, how much curl and how hard -- and
kick. The ball flies as a real one does: the air slows it, spin bends
it, wind carries it. It has to cross the goal line inside the ring,
past the wall and out of the keeper's reach. One kick a round.

* rung 1: the flight the kick would take is drawn before kicking; a
  big ring, no wall, no keeper;
* rungs 2-3: the flight is drawn at rung 2, not at rung 3; the ring
  smaller;
* rungs 4-6: a wall and a keeper;
* rungs 7-9: wind, shown by a flag;
* rungs 10-12: the kick is taken from off to the side, the wall jumps,
  the keeper is quicker;
* rungs 13 and up: the ring shrinks every rung, the wind strengthens,
  and the keeper quickens, without end.

For the agent boundary: ports 0-7 turn the aim left and right, raise
and lower it, curl it left and right, and kick harder and softer, for
the step they are sent in; port 8 kicks.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

(AIM_L, AIM_R, RAISE, LOWER, CURL_L, CURL_R, HARDER, SOFTER, KICK) = range(9)
PORTS = 9
EVENTS = (KICK,)
WIDE, HIGH = 7.32, 2.44            # the goal mouth
BALL = 0.11
DRAG = 0.013                       # per metre: a = -DRAG |v| v
LIFT = 0.012                       # the spin's bend: a = LIFT w x v
RATES = {AIM_L: -6.0, AIM_R: 6.0, RAISE: 5.0, LOWER: -5.0,
         CURL_L: 8.0, CURL_R: -8.0, HARDER: 6.0, SOFTER: -6.0}
LIMITS = {'aim': (-35.0, 35.0), 'lift': (0.0, 40.0), 'curl': (-14.0, 14.0),
          'power': (8.0, 34.0)}
WALL_AT = 9.15
FLIGHT_DT = 1 / 120.0
PATCHES = ('wood', 'bell', 'growl')


class Grade(NamedTuple):
    rung: int
    guide: bool
    ring: float
    wall: int                  # defenders in the wall
    jump: float                # how high the wall jumps
    keeper: float              # the keeper's speed, or 0
    wind: float
    side: float                # how far off to the side the kick is
    distance: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, True, 1.2, 0, 0.0, 0.0, 0.0, 0.0, 18.0)
    if r < 4:
        return Grade(r, r == 2, 1.0 if r == 2 else 0.9, 0, 0.0, 0.0, 0.0,
                     0.0, 19.0)
    if r < 7:
        return Grade(r, False, 0.85 - 0.05 * (r - 4), 3, 0.0, 2.5, 0.0, 0.0,
                     20.0)
    if r < 10:
        return Grade(r, False, 0.65 - 0.03 * (r - 7), 4, 0.0, 3.0,
                     2.0 + (r - 7), 0.0, 21.0)
    if r < 13:
        return Grade(r, False, 0.55 - 0.03 * (r - 10), 4, 0.25, 3.5, 4.0,
                     6.0, 22.0)
    return Grade(r, False, max(0.16, 0.48 * 0.92 ** (r - 13)), 4, 0.3,
                 min(4.0, 3.6 + 0.02 * (r - 13)), min(8.0, 4.0 + 0.2 *
                                                      (r - 13)),
                 8.0, min(25.0, 22.0 + 0.2 * (r - 13)))


class Pitch(NamedTuple):
    level: Grade
    spot: Tuple[float, float]           # the ball's x, z
    goal_x: float                       # the goal's middle; the line at z=0
    ring: Tuple[float, float, float]    # x, y on the goal mouth, radius
    wall: Tuple[float, float, float, float]   # x middle, z, half width, h
    keeper: float                       # the keeper's x
    wind: Tuple[float, float]           # x, z
    seconds: float


class Kick(NamedTuple):
    aim: float
    lift: float
    curl: float
    power: float


START = Kick(0.0, 12.0, 0.0, 18.0)


def launch(p: Pitch, k: Kick):
    """The ball's first velocity: *aim* is degrees off the line from
    the spot to the goal's middle."""
    sx, sz = p.spot
    base = math.atan2(p.goal_x - sx, sz)           # toward the goal: -z
    a = base + math.radians(k.aim)
    e = math.radians(k.lift)
    return (k.power * math.cos(e) * math.sin(a), k.power * math.sin(e),
            -k.power * math.cos(e) * math.cos(a))


def fly(p: Pitch, k: Kick, keep: bool = False):
    """The flight: (where it crossed the line or None, how, the path).
    *how* is 'wall', 'short' or 'line'."""
    x, y, z = p.spot[0], BALL, p.spot[1]
    vx, vy, vz = launch(p, k)
    w = k.curl
    wx, wz = p.wind
    path = [(0.0, x, y, z)] if keep else None
    t = 0.0
    dt = FLIGHT_DT
    wall_x, wall_z, wall_w, wall_h = p.wall
    passed_wall = p.level.wall == 0
    while t < 4.0:
        rx, ry, rz = vx - wx, vy, vz - wz
        sp = math.sqrt(rx * rx + ry * ry + rz * rz)
        ax = -DRAG * sp * rx + LIFT * (-w) * rz * -1.0
        az = -DRAG * sp * rz + LIFT * (-w) * -rx * -1.0
        ay = -DRAG * sp * ry - 9.81
        vx, vy, vz = vx + ax * dt, vy + ay * dt, vz + az * dt
        nx, ny, nz = x + vx * dt, y + vy * dt, z + vz * dt
        t += dt
        if not passed_wall and nz <= wall_z < z:
            s = (z - wall_z) / (z - nz)
            cx, cy = x + (nx - x) * s, y + (ny - y) * s
            if abs(cx - wall_x) < wall_w + BALL and cy < wall_h + BALL:
                if keep:
                    path.append((t, cx, cy, wall_z))
                return (cx, cy, t), 'wall', path
            passed_wall = True
        if nz <= 0.0 < z:
            s = z / (z - nz)
            cx, cy = x + (nx - x) * s, y + (ny - y) * s
            if keep:
                path.append((t, cx, cy, 0.0))
            return (cx, cy, t - dt * (1 - s)), 'line', path
        x, y, z = nx, max(BALL, ny), nz
        if ny < BALL:
            vy = -vy * 0.5
            vx, vz = vx * 0.8, vz * 0.8
        if keep:
            path.append((t, x, y, z))
    return None, 'short', path


def keeper_reach(p: Pitch, cross) -> bool:
    """Whether the keeper gets to a ball crossing at (x, y) at time t."""
    lv = p.level
    if not lv.keeper:
        return False
    x, y, t = cross
    move = max(0.0, t - 0.3) * lv.keeper
    gap = abs(x - p.keeper)
    reach = 1.0 if y < 1.9 else 0.7
    return gap - move < reach and y < 2.6


def judge(p: Pitch, k: Kick) -> Tuple[bool, str]:
    cross, how, _path = fly(p, k)
    if how == 'wall':
        return False, _('Into the wall')
    if cross is None:
        return False, _('Fell short')
    x, y, t = cross
    if abs(x - p.goal_x) > WIDE / 2 - BALL or y > HIGH - BALL:
        return False, _('Wide of the goal') if y <= HIGH - BALL else \
            _('Over the bar')
    if keeper_reach(p, cross):
        return False, _('Saved')
    rx, ry, rr = p.ring
    if math.hypot(x - rx, y - ry) > rr:
        return False, _('In the goal, but %.1f m from the ring') % (
            math.hypot(x - rx, y - ry) - rr)
    return True, _('In the ring')


def _solve(p: Pitch, curl: float, power: float, k0=None):
    """Aim and lift that put the ball on the ring's middle, by Newton."""
    rx, ry, _rr = p.ring
    aim, lift = (k0.aim, k0.lift) if k0 else (0.0, 12.0)
    for _i in range(12):
        k = Kick(aim, lift, curl, power)
        c, how, _p = fly(p, k)
        if c is None or how == 'wall':
            # pretend the wall is not there to find the line
            q = p._replace(level=p.level._replace(wall=0))
            c, how, _p = fly(q, k)
            if c is None:
                lift += 4.0
                continue
        ex, ey = rx - c[0], ry - c[1]
        if abs(ex) < 0.01 and abs(ey) < 0.01:
            return k
        q = p._replace(level=p.level._replace(wall=0))
        c1 = fly(q, Kick(aim + 0.2, lift, curl, power))[0]
        c2 = fly(q, Kick(aim, lift + 0.2, curl, power))[0]
        if c1 is None or c2 is None:
            lift += 2.0
            continue
        j = ((c1[0] - c[0]) / 0.2, (c2[0] - c[0]) / 0.2,
             (c1[1] - c[1]) / 0.2, (c2[1] - c[1]) / 0.2)
        det = j[0] * j[3] - j[1] * j[2]
        if abs(det) < 1e-9:
            return None
        da = (ex * j[3] - j[1] * ey) / det
        dl = (j[0] * ey - ex * j[2]) / det
        aim += max(-8, min(8, da))
        lift += max(-8, min(8, dl))
        if not (LIMITS['aim'][0] <= aim <= LIMITS['aim'][1]) or \
                not (LIMITS['lift'][0] <= lift <= LIMITS['lift'][1]):
            return None
    return None


def plan(p: Pitch):
    """A kick that scores, if one is found."""
    for power in (22.0, 26.0, 30.0, 18.0, 33.0, 15.0):
        for curl in (0.0, 6.0, -6.0, 10.0, -10.0, 3.0, -3.0):
            k = _solve(p, curl, power)
            if k is not None and judge(p, k)[0]:
                return k
    return None


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Pitch:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(200):
        side = draw.uniform(-1, 1) * level.side
        spot = (side, level.distance)
        goal_x = 0.0
        corner = draw.choice((-1, 1))
        if level.keeper:
            rx = corner * draw.uniform(1.6, WIDE / 2 - level.ring * 0.5 - 0.2)
            ry = draw.uniform(max(0.4, level.ring * 0.7), HIGH - 0.35)
        else:
            rx = draw.uniform(-WIDE / 2 + level.ring, WIDE / 2 - level.ring)
            ry = draw.uniform(max(0.4, level.ring * 0.7),
                              max(0.5, HIGH - level.ring * 0.7))
        ring = (rx, ry, level.ring)
        # the wall stands on the line from the ball to the ring's side
        to = (rx - spot[0], -spot[1])
        frac = (spot[1] - WALL_AT) / spot[1]
        wall_x = spot[0] + to[0] * (1 - frac) + draw.uniform(-0.4, 0.4)
        wall = (wall_x, WALL_AT if level.wall else -99.0,
                0.3 * level.wall, 1.8 + level.jump)
        keeper = -corner * draw.uniform(0.0, 0.8) if level.keeper else 0.0
        a = draw.uniform(0, 2 * math.pi)
        wind = (level.wind * math.cos(a), level.wind * math.sin(a))
        p = Pitch(level, spot, goal_x, ring, wall, keeper, wind, 30.0)
        if judge(p, START)[0]:
            continue
        if plan(p) is not None and play(p)[0]:
            return p
    raise RuntimeError('free kick: no pitch for rung %d' % rung)


class Run(object):
    def __init__(self, p: Pitch) -> None:
        self.p = p
        self.level = p.level
        self.t = 0.0
        self.kick = START
        self.kicked: Optional[float] = None
        self.path = None
        self.outcome: Optional[Tuple[bool, str]] = None
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = p.seconds + 5.0

    def ball(self) -> Tuple[float, float, float]:
        if self.kicked is None or not self.path:
            return (self.p.spot[0], BALL, self.p.spot[1])
        dt = self.t - self.kicked
        for t, x, y, z in self.path:
            if t >= dt:
                return (x, y, z)
        return self.path[-1][1:]

    def keeper_x(self) -> float:
        p = self.p
        if self.kicked is None or not p.level.keeper or not self.path:
            return p.keeper
        dt = self.t - self.kicked
        goal = self.path[-1][1]
        move = max(0.0, dt - 0.3) * p.level.keeper
        gap = goal - p.keeper
        return p.keeper + math.copysign(min(abs(gap), move), gap)

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.kicked is None:
            if isinstance(control, int) and control in RATES:
                k = self.kick
                rate = RATES[control] * dt
                field = ('aim' if control in (AIM_L, AIM_R) else
                         'lift' if control in (RAISE, LOWER) else
                         'curl' if control in (CURL_L, CURL_R) else 'power')
                lo, hi = LIMITS[field]
                self.kick = k._replace(**{field: max(lo, min(
                    hi, getattr(k, field) + rate))})
            if self.t > self.p.seconds:
                self.result = (False, _('Out of time'))
            return
        if self.path and self.t - self.kicked >= self.path[-1][0] + 0.6:
            self.result = self.outcome

    def strike(self) -> None:
        if self.kicked is not None or self.result is not None:
            return
        self.kicked = self.t
        self.outcome = judge(self.p, self.kick)
        self.path = fly(self.p, self.kick, keep=True)[2]
        self._note(0.12, 160.0, 0, 0.5)
        self.notes.append(Note(self.t + self.path[-1][0], 0.3,
                               1320.0 if self.outcome[0] else 110.0, 0.0,
                               0.0, 0.3, 0.3, 0.8,
                               1 if self.outcome[0] else 2,
                               len(self.notes) + 1, -1, 0.0))


def act(run: Run, port: int) -> None:
    if port == KICK:
        run.strike()


def autopilot(run: Run) -> List[int]:
    """Finds a kick that scores, sets each dial to it in turn, checks
    the kick as set, and kicks."""
    if run.result is not None or run.kicked is not None:
        return []
    want = getattr(run, '_want', None)
    if want is None:
        want = run._want = plan(run.p)
        if want is None:
            return [KICK]
    k = run.kick
    for field, up, down in (('power', HARDER, SOFTER),
                            ('curl', CURL_L, CURL_R),
                            ('aim', AIM_R, AIM_L), ('lift', RAISE, LOWER)):
        step = abs(RATES[up]) / 30.0
        err = getattr(want, field) - getattr(k, field)
        if abs(err) > step / 2:
            return [up if err > 0 else down]
    if judge(run.p, k)[0]:
        return [KICK]
    # the dials could not land exactly: aim again from where they are
    again = _solve(run.p, k.curl, k.power, k)
    run._want = again if again is not None else plan(run.p)
    if run._want is None:
        return [KICK]
    tries = getattr(run, '_tries', 0) + 1
    run._tries = tries
    if tries > 6:
        return [KICK]
    return []


def play(p: Pitch, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(p)
    while run.result is None:
        ports = pilot(run)
        held = [q for q in ports if q not in EVENTS]
        for q in ports:
            if q in EVENTS:
                act(run, q)
        run.step(dt, held[0] if held else None)
    return run.result
