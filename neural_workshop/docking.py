# -*- coding: utf-8 -*-
"""Docking: bring the craft into the station's port.

There is no friction in space: a push starts a drift that lasts until
an equal push the other way stops it, and a spin goes on until it is
stopped too. The view is from the cockpit, along the craft's nose: the
station ahead, its port, and on the port a cross on a post standing out
from a ring -- when the cross sits in the middle of the ring the craft
is in line with the port, when it does not, the way it is off shows
the way to go. Touch the port square on, centred, and slowly.

* rung 1: the craft drifts slowly toward the port, a little to one
  side: push across to line up, push back to stop the drift across;
  range and closing speed are shown;
* rungs 2-3: off to the side and up or down;
* rungs 4-6: the craft starts still and far off: get it moving, and
  slow it before contact;
* rungs 7-9: the nose is turned off the line and turning: square it
  up (a push now goes where the nose points); the readouts are gone;
* rungs 10-12: the station turns about the docking line, and the craft
  has to turn with it;
* rungs 13 and up: tighter limits and faster spins, to what a careful
  pilot can still meet; further off every rung; and less fuel without
  end: each approach gets what the reference pilot burns on it, times a
  margin that falls from three times on rung 1 toward a tenth more.

For the agent boundary: ports 0-5 push left, right, down, up, forward
and back; 6-7 turn the nose left and right, 8-9 down and up, 10-11
roll left and right -- each for the step it is sent in.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

(LEFT, RIGHT, DOWN, UP, FORE, AFT, YAW_L, YAW_R, PITCH_D, PITCH_U,
 ROLL_L, ROLL_R) = range(12)
PORTS = 12
EVENTS = ()
PUSH = 0.12                    # metres a second, a second
TURN = 0.12                    # radians a second, a second
PATCHES = ('wood', 'bell', 'growl')


class Grade(NamedTuple):
    rung: int
    lateral: Tuple[float, float]   # starting offset across and up
    drift: float                   # starting closing speed
    far: float                     # starting range
    nose: float                    # starting angle off, radians
    spin: float                    # starting turn rate
    station: float                 # station's roll rate
    readouts: bool
    tol: float                     # metres off centre at contact
    vmax: float                    # closing speed at contact
    angle: float                   # radians off square at contact
    slack: float                   # fuel, as a multiple of what the
                                   # reference burns on the approach


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, (1.2, 0.0), 0.25, 12, 0, 0, 0, True, 0.35, 0.5,
                     0.2, 3.0)
    if r < 4:
        return Grade(r, (1.2, 1.0), 0.25, 14, 0, 0, 0, True, 0.3, 0.45,
                     0.15, 2.8)
    if r < 7:
        return Grade(r, (1.5, 1.2), 0.0, 18 + 2 * (r - 4), 0, 0, 0, True,
                     0.25, 0.35, 0.12, 2.5)
    if r < 10:
        return Grade(r, (1.5, 1.2), 0.0, 20, math.radians(6),
                     math.radians(1.0), 0, False, 0.22, 0.3, 0.08, 2.2)
    if r < 13:
        return Grade(r, (1.5, 1.5), 0.0, 22, math.radians(8),
                     math.radians(1.5), math.radians(1.5 + 0.5 * (r - 10)),
                     False, 0.2, 0.3, 0.07, 2.0)
    k = 0.95 ** (r - 13)
    return Grade(r, (2.0, 2.0), 0.0, 24 + (r - 13), math.radians(10),
                 math.radians(min(3.0, 2 + 0.1 * (r - 13))),
                 math.radians(min(4.0, 2.5 + 0.2 * (r - 13))), False,
                 max(0.12, 0.2 * k), max(0.18, 0.3 * k), max(0.045, 0.07 * k),
                 1.1 + 0.8 * 0.95 ** (r - 13))


def body_to_world(v, yaw: float, pitch: float, roll: float):
    """A vector in the craft's frame (x right, y up, z ahead) in the
    station's (z along the docking line)."""
    x, y, z = v
    cr, sr = math.cos(roll), math.sin(roll)
    x, y = x * cr - y * sr, x * sr + y * cr
    cp, sp = math.cos(pitch), math.sin(pitch)
    y, z = y * cp + z * sp, -y * sp + z * cp
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, z = x * cy + z * sy, -x * sy + z * cy
    return x, y, z


def world_to_body(v, yaw: float, pitch: float, roll: float):
    """The other way: a station vector as the craft sees it."""
    x, y, z = v
    cy, sy = math.cos(-yaw), math.sin(-yaw)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cp, sp = math.cos(-pitch), math.sin(-pitch)
    y, z = y * cp + z * sp, -y * sp + z * cp
    cr, sr = math.cos(-roll), math.sin(-roll)
    x, y = x * cr - y * sr, x * sr + y * cr
    return x, y, z


class Approach(NamedTuple):
    level: Grade
    pos: Tuple[float, float, float]
    vel: Tuple[float, float, float]
    att: Tuple[float, float, float]       # yaw, pitch, roll
    spin: Tuple[float, float, float]
    roll0: float                          # the station's roll at start
    fuel: float = 1e9                     # seconds of thrust


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Approach:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(100):
        sx = draw.choice((-1, 1)) * level.lateral[0] * draw.uniform(0.7, 1)
        sy = draw.choice((-1, 1)) * level.lateral[1] * draw.uniform(0.7, 1)
        pos = (sx, sy, -level.far)
        vel = (0.0, 0.0, level.drift)
        att = tuple(draw.choice((-1, 1)) * level.nose * draw.uniform(0.6, 1)
                    for _a in range(2)) + (
            draw.uniform(-0.3, 0.3) if level.station else 0.0,)
        spin = tuple(draw.uniform(-1, 1) * level.spin for _a in range(3))
        ap = Approach(level, pos, vel, att, spin,
                      draw.uniform(0, 2 * math.pi) if level.station else 0.0)
        run = Run(ap)
        while run.result is None:
            ports = autopilot(run)
            run.step(1 / 30.0, ports[0] if ports else None)
        if not run.result[0]:
            continue
        used = 1e9 - run.fuel
        ap = ap._replace(fuel=used * level.slack + 3.0)
        if play(ap)[0]:
            return ap
    raise RuntimeError('docking: no approach for rung %d' % rung)


class Run(object):
    def __init__(self, ap: Approach) -> None:
        self.ap = ap
        self.level = ap.level
        self.t = 0.0
        self.pos = list(ap.pos)
        self.vel = list(ap.vel)
        self.att = list(ap.att)
        self.spin = list(ap.spin)
        self.fuel = ap.fuel
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = 240.0

    def station_roll(self) -> float:
        return self.ap.roll0 + self.level.station * self.t

    def roll_error(self) -> float:
        """The craft's roll against the station's, folded to a quarter
        turn: the port looks the same every quarter turn."""
        d = self.att[2] - self.station_roll()
        q = math.pi / 2
        return (d + q / 2) % q - q / 2

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        on = {control} if isinstance(control, int) else set(control or ())
        if on and self.fuel > 0:
            self.fuel -= dt * len(on)
            push = [0.0, 0.0, 0.0]
            for port, axis, sign in ((LEFT, 0, -1), (RIGHT, 0, 1),
                                     (DOWN, 1, -1), (UP, 1, 1),
                                     (FORE, 2, 1), (AFT, 2, -1)):
                if port in on:
                    push[axis] += sign * PUSH
            w = body_to_world(push, *self.att)
            for i in range(3):
                self.vel[i] += w[i] * dt
            for port, axis, sign in ((YAW_L, 0, -1), (YAW_R, 0, 1),
                                     (PITCH_D, 1, -1), (PITCH_U, 1, 1),
                                     (ROLL_L, 2, 1), (ROLL_R, 2, -1)):
                if port in on:
                    self.spin[axis] += sign * TURN * dt
        for i in range(3):
            self.pos[i] += self.vel[i] * dt
            self.att[i] += self.spin[i] * dt
        if self.pos[2] >= 0.0:
            self._contact()
        elif self.pos[2] < -self.level.far - 15 or self.t > self.end:
            self.result = (False, _('Drifted away'))

    def _contact(self) -> None:
        lv = self.level
        off = math.hypot(self.pos[0], self.pos[1])
        v = self.vel[2]
        square = max(abs(self.att[0]), abs(self.att[1]))
        problems = []
        if off > lv.tol:
            problems.append(_('%.2f m off centre') % off)
        if v > lv.vmax:
            problems.append(_('%.2f m/s too fast') % v)
        if square > lv.angle:
            problems.append(_('nose %.0f degrees off') % math.degrees(square))
        if lv.station and abs(self.roll_error()) > lv.angle:
            problems.append(_('rolled %.0f degrees off') %
                            math.degrees(abs(self.roll_error())))
        if problems:
            self.result = (False, _('Hit the port: ') + ', '.join(problems))
            self._note(0.5, 90.0, 2, 0.5)
        else:
            self.result = (True, _('Docked at %.2f m/s') % v)
            self._note(0.4, 880.0, 1, 0.3)


def act(run: Run, port: int) -> None:
    pass


def _ask(err: float, rate: float, k: float, top: float, eps: float
         ) -> Tuple[float, int]:
    """How badly an axis wants a push, and which way: the rate it should
    have to close its error, against the rate it has."""
    want = max(-top, min(top, -k * err))
    miss = want - rate
    return (abs(miss) / eps, 1 if miss > 0 else -1)


def autopilot(run: Run) -> List[int]:
    """Squares the nose, matches the station's roll, centres, then
    closes at a speed that falls with the range: one push a step, on
    the axis furthest from what it should be doing."""
    if run.result is not None:
        return []
    lv = run.level
    yaw, pitch, roll = run.att
    # where the port is and how the craft moves, as the craft sees them
    x, y, z = world_to_body(run.pos, yaw, pitch, roll)
    vx, vy, vz = world_to_body(run.vel, yaw, pitch, roll)
    wy, wp, wr = run.spin
    asks = []
    # how fine to be: finer the tighter the port's limits
    ea, el = 0.004, 0.012
    asks.append(_ask(yaw, wy, 0.5, 0.06, ea) + ((YAW_L, YAW_R),))
    asks.append(_ask(pitch, wp, 0.5, 0.06, ea) + ((PITCH_D, PITCH_U),))
    if lv.station:
        want = lv.station - 0.5 * run.roll_error()
        miss = want - wr
        asks.append((abs(miss) / ea, 1 if miss > 0 else -1,
                     (ROLL_R, ROLL_L)))
    # across and up, in the craft's own frame
    asks.append(_ask(x, vx, 0.25, 0.25, el) + ((LEFT, RIGHT),))
    asks.append(_ask(y, vy, 0.25, 0.25, el) + ((DOWN, UP),))
    centred = math.hypot(x, y) < lv.tol * 0.4 and \
        max(abs(yaw), abs(pitch)) < lv.angle * 0.5
    # the limit is at contact: come in faster, slowing as the range
    # closes, and hold off at the last few metres until centred
    top = min(0.8, lv.vmax * 0.6 + 0.05 * max(0.0, abs(z) - 1.0)) if (
        centred or abs(z) > 6) else 0.0
    miss = top - vz
    asks.append((abs(miss) / 0.012, 1 if miss > 0 else -1, (AFT, FORE)))
    need, sign, ports = max(asks, key=lambda a: a[0])
    if need < 1.0:
        return []
    return [ports[1] if sign > 0 else ports[0]]


def play(ap: Approach, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(ap)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
