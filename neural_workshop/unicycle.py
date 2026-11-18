# -*- coding: utf-8 -*-
"""Unicycle: ride a wobbling rider on one wheel across open country to
the flags.

A rider sits on a unicycle in a wide field. The rider is joined to the
wheel by a springy body, so every bump shakes them and every pedal
stroke rocks them back; and they can topple sideways too, so balance has
to be kept in all four directions. Pedal and back-pedal the wheel; lean
forward and back; lean left and right -- and as on a real unicycle (or
a bicycle) a sideways lean also turns the wheel that way, which is how
you steer. Ride to each flag in turn. Only the head touching the ground
ends the ride.

* rungs 1-8: soft gravity, gentle pedalling and leaning, and training
  wheels: a pull back to upright and a damper on the rider's sway. On
  rungs 1 and 2 the rider rights themselves if left alone; from rung 3
  the pull is well under gravity, and from rung 8 it is gone.
  Everything firms up a little each rung (full strength from rung 9);
* rung 1: flat ground, one flag straight ahead, plenty of time;
* rungs 2-3: gentle hills, the flag off to one side;
* rungs 4-6: steeper hills and small bumps, two flags;
* rungs 7-9: steps up and down;
* rungs 10-12: ledges to ride off, three flags and sharper turns;
* rungs 13 and up: the ride grows longer and rougher, and the time
  allowed closes in on what the best ride takes, without end.

For the agent boundary: ports 0-1 pedal and back-pedal; 2-3 lean back
and forward; 4-7 pedal or back-pedal while leaning back or forward; 8-9
lean (and so turn) left and right; each for the step it is sent in.

The world: x and z along the ground, y up; a heading of 0 is along +x,
and the rider's right is then +z, so turning right turns the heading
up (from +x towards +z). Seen from behind with y up, that is the
screen's right, as a right-handed camera draws it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

(PEDAL, BACK, LEAN_B, LEAN_F, PEDAL_B, PEDAL_F, BACK_B, BACK_F, LEAN_L,
 LEAN_R) = range(10)
PORTS = 10
EVENTS = ()
DRIVE = {PEDAL: 1, BACK: -1, PEDAL_B: 1, PEDAL_F: 1, BACK_B: -1, BACK_F: -1}
LEAN = {LEAN_B: -1, LEAN_F: 1, PEDAL_B: -1, PEDAL_F: 1, BACK_B: -1,
        BACK_F: 1}
SIDE = {LEAN_L: -1, LEAN_R: 1}
R = 0.35                       # the wheel
MW, MR = 6.0, 50.0             # wheel and rider
IW = 0.5 * MW * R * R
POST = 1.0                     # the body's rest length, axle to rider
HEAD = 1.5                     # the head, as a share of the body
K, C = 7000.0, 500.0           # the body's spring and damping
TORQUE = 100.0
SPIN = 13.0                    # the wheel's top speed, radians a second
LEAN_F_N = 450.0               # the lean, newtons on the rider
GRAV = 9.81
G_SOFT = 0.7                   # gravity at rung 1
GRIP = 1.2
SUB = 4
SIDE_H = 1.1                   # the height the rider topples sideways from
SIDE_A = 3.2                   # a sideways lean, radians a second squared
TURN = 1.6                     # how a lean turns: the turn's radius is
                               # TURN / tan(lean) metres
REACH = 1.5                    # how near a flag counts as there
DX = 0.25                      # the ground's grid
MARGIN = 14.0                  # ground beyond the flags, all round
PATCHES = ('wood', 'bell', 'growl')


def gentle(rung: int) -> float:
    """How much the ladder's bottom is softened: 1 at rung 1, falling
    by an eighth a rung, nothing from rung 9."""
    return max(0.0, min(1.0, (9 - int(rung)) / 8.0))


class Grade(NamedTuple):
    rung: int
    length: float              # the ride, start to last flag
    hills: float               # the swell's height
    bumps: float               # small bumps' height
    steps: float               # steps' height, or 0
    pits: int                  # ledges to ride off
    slack: float               # time allowed over the reference's
    flags: int = 1
    turn: float = 0.0          # how far round each flag lies, radians
    gravity: float = GRAV
    soft: float = 1.0          # pedalling and leaning, as a share of full
    steady: float = 0.0        # training wheels: a pull back to upright
    damp: float = 0.0          # and a damper on the rider's sway


def assist(rung: int) -> float:
    """The training wheels, as a share of gravity: more than gravity on
    rungs 1 and 2 (the rider rights themselves), then well under it, and
    gone from rung 8."""
    return {1: 1.3, 2: 1.1, 3: 0.6, 4: 0.45, 5: 0.3, 6: 0.18,
            7: 0.08}.get(int(rung), 0.0)


def grade(rung: int) -> Grade:
    level = _grade(rung)
    ease = gentle(level.rung)
    g = GRAV * (G_SOFT / GRAV) ** ease
    r = level.rung
    return level._replace(
        gravity=g, soft=(g / GRAV) ** 0.85,
        steady=g * assist(r), damp=3.0 * ease,
        slack=level.slack * (1.0 + 0.6 * ease),
        flags=1 if r < 4 else 2 if r < 10 else 3 + min(2, (r - 10) // 8),
        turn=(0.0 if r == 1 else 0.45 if r < 4 else 0.8 if r < 10
              else min(1.2, 1.0 + 0.02 * (r - 10))))


def _grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, 16.0, 0.0, 0.0, 0.0, 0, 3.0)
    if r < 4:
        return Grade(r, 22.0, 0.5 + 0.3 * (r - 2), 0.0, 0.0, 0, 2.5)
    if r < 7:
        return Grade(r, 32.0, 1.2 + 0.2 * (r - 4), 0.06 + 0.02 * (r - 4),
                     0.0, 0, 2.2)
    if r < 10:
        return Grade(r, 38.0, 1.4, 0.08, 0.15 + 0.05 * (r - 7), 0, 2.0)
    if r < 13:
        return Grade(r, 45.0, 1.4, 0.08, 0.2, 1 + (r - 10) // 2, 1.8)
    return Grade(r, min(120.0, 50.0 + 3.0 * (r - 13)),
                 min(3.0, 1.5 + 0.05 * (r - 13)),
                 min(0.16, 0.09 + 0.004 * (r - 13)),
                 min(0.3, 0.2 + 0.005 * (r - 13)), 2 + (r - 13) // 6,
                 max(1.08, 1.1 + 0.6 * 0.9 ** (r - 13)))


class Track(NamedTuple):
    """The field: its flags and the ground's height on a grid."""
    level: Grade
    flags: Tuple[Tuple[float, float], ...]
    x0: float
    z0: float
    nx: int
    nz: int
    heights: Tuple[float, ...]       # row by row along z
    seconds: float
    best: float                      # the reference's time

    @property
    def finish(self) -> Tuple[float, float]:
        return self.flags[-1]


def height(tr: Track, x: float, z: float) -> float:
    """The ground's height at (x, z): bilinear on the grid, level beyond
    its edge."""
    fx = max(0.0, min(tr.nx - 1.001, (x - tr.x0) / DX))
    fz = max(0.0, min(tr.nz - 1.001, (z - tr.z0) / DX))
    i, j = int(fx), int(fz)
    u, v = fx - i, fz - j
    h = tr.heights
    a = h[j * tr.nx + i]
    b = h[j * tr.nx + i + 1]
    c = h[(j + 1) * tr.nx + i]
    d = h[(j + 1) * tr.nx + i + 1]
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def _route(level: Grade, draw) -> List[Tuple[float, float]]:
    flags = []
    x = z = 0.0
    heading = 0.0
    each = level.length / level.flags
    for k in range(level.flags):
        if level.turn:
            heading += draw.choice((-1, 1)) * draw.uniform(
                0.5 * level.turn, level.turn)
        d = each * draw.uniform(0.85, 1.15)
        x, z = x + d * math.cos(heading), z + d * math.sin(heading)
        flags.append((round(x, 2), round(z, 2)))
    return flags


def _ground(level: Grade, flags, draw):
    """The height grid: swells, bumps, steps and ledges across the way."""
    xs = [0.0] + [f[0] for f in flags]
    zs = [0.0] + [f[1] for f in flags]
    x0, z0 = min(xs) - MARGIN, min(zs) - MARGIN
    nx = int((max(xs) + MARGIN - x0) / DX) + 2
    nz = int((max(zs) + MARGIN - z0) / DX) + 2
    waves = [(level.hills * draw.uniform(0.25, 0.45),
              draw.uniform(0.12, 0.3), draw.uniform(0.12, 0.3),
              draw.uniform(0, 6.3), draw.uniform(0, 6.3))
             for _w in range(2)] if level.hills else []
    legs = list(zip([(0.0, 0.0)] + flags[:-1], flags))
    bumps = []
    if level.bumps:
        for (ax, az), (bx, bz) in legs:
            d = math.hypot(bx - ax, bz - az)
            s = 5.0
            while s < d - 1.0:
                u = s / d
                side = draw.uniform(-1.5, 1.5)
                px = ax + (bx - ax) * u - (bz - az) / d * side
                pz = az + (bz - az) * u + (bx - ax) / d * side
                bumps.append((px, pz, level.bumps * draw.uniform(0.6, 1.0)))
                s += draw.uniform(2.0, 5.0)
    edges = []                       # (point, unit normal, rise, width)
    for (ax, az), (bx, bz) in legs:
        d = math.hypot(bx - ax, bz - az)
        n = ((bx - ax) / d, (bz - az) / d)
        if level.steps:
            s = 7.0
            while s < d - 4.0:
                s += draw.uniform(5.0, 9.0)
                if s >= d - 3.0:
                    break
                edges.append(((ax + n[0] * s, az + n[1] * s), n,
                              level.steps * draw.uniform(0.6, 1.0)
                              * draw.choice((-1, 1)), 0.75))
    if level.pits:
        (ax, az), (bx, bz) = legs[-1] if len(legs) == 1 else \
            max(legs, key=lambda l: math.hypot(l[1][0] - l[0][0],
                                               l[1][1] - l[0][1]))
        d = math.hypot(bx - ax, bz - az)
        n = ((bx - ax) / d, (bz - az) / d)
        span = (d - 12) / level.pits
        for k in range(level.pits):
            s = 8.0 + span * (k + draw.uniform(0.35, 0.65))
            h = min(1.4, draw.uniform(0.5, 0.8) +
                    0.03 * max(0, level.rung - 13))
            edges.append(((ax + n[0] * s, az + n[1] * s), n, -h, 0.25))
    heights = []
    for j in range(nz):
        z = z0 + j * DX
        for i in range(nx):
            x = x0 + i * DX
            ease = min(1.0, max(0.0, (math.hypot(x, z) - 3.0) / 4.0))
            y = 0.0
            for a, kx, kz, px, pz in waves:
                y += a * math.sin(kx * x + px) * math.sin(kz * z + pz)
            y *= ease
            for bx, bz, h in bumps:
                dd = math.hypot(x - bx, z - bz)
                if dd < 0.4:
                    y += h * (1 - dd / 0.4)
            for (px, pz), (ux, uz), rise, width in edges:
                across = (x - px) * ux + (z - pz) * uz
                if across > 0:
                    y += rise * min(1.0, across / width)
            heights.append(round(y, 4))
    return x0, z0, nx, nz, tuple(heights)


# --- the rider ------------------------------------------------------------------

class Body(NamedTuple):
    """The rider in their own upright plane, plus where that plane is.

    px, py, vx, vy: the axle along the heading and up, and its speed;
    a, w: the wheel's turn and spin; qx, qy, ux, uy: the body's point
    and its speed, in the same plane; roll, rate: the sideways lean
    (right positive); x, z, heading: where the plane stands in the field
    (px is kept at nought, the plane moved along instead)."""
    px: float
    py: float
    vx: float
    vy: float
    a: float
    w: float
    qx: float
    qy: float
    ux: float
    uy: float
    roll: float = 0.0
    rate: float = 0.0
    x: float = 0.0
    z: float = 0.0
    heading: float = 0.0


def along(tr: Track, b: Body, s: float) -> float:
    """The ground's height *s* metres ahead of the wheel, along the
    heading."""
    c, n = math.cos(b.heading), math.sin(b.heading)
    return height(tr, b.x + (s - b.px) * c, b.z + (s - b.px) * n)


def begin(tr: Track) -> Body:
    y = height(tr, 0.0, 0.0) + R
    lean = 0.03       # never quite upright: left alone, the rider tips
    return Body(0.0, y, 0.0, 0.0, 0.0, 0.0, POST * math.sin(lean),
                y + POST * math.cos(lean), 0.0, 0.0, 0.02, 0.0)


def _contact(tr: Track, b: Body, px, py, vx, vy, w, dt, grav):
    """The wheel against the ground: pushed out, its fall stopped, and
    rolling with grip."""
    best = None
    s = px - R - 0.3
    prev = (s, along(tr, b, s))
    while s < px + R + 0.3:
        s += DX
        here = (s, along(tr, b, s))
        (ax, ay), (bx, by) = prev, here
        ex, ey = bx - ax, by - ay
        u = max(0.0, min(1.0, ((px - ax) * ex + (py - ay) * ey) /
                         (ex * ex + ey * ey)))
        cx, cy = ax + ex * u, ay + ey * u
        d = math.hypot(px - cx, py - cy)
        if d < R and (best is None or d < best[0]):
            best = (d, cx, cy)
        prev = here
    if best is None:
        return px, py, vx, vy, w
    d, cx, cy = best
    nx, ny = ((px - cx) / d, (py - cy) / d) if d > 1e-9 else (0.0, 1.0)
    px, py = cx + nx * R, cy + ny * R
    vn = vx * nx + vy * ny
    jn = 0.0
    if vn < 0:
        vx -= 1.05 * vn * nx
        vy -= 1.05 * vn * ny
        jn = -1.05 * vn * MW
    tx, ty = ny, -nx
    slip = vx * tx + vy * ty + w * R
    meff = 1.0 / (1.0 / MW + R * R / IW)
    jt = -slip * meff
    cap = GRIP * (jn + MW * grav * dt)
    jt = max(-cap, min(cap, jt))
    vx += jt / MW * tx
    vy += jt / MW * ty
    w += jt * R / IW
    return px, py, vx, vy, w


def advance(tr: Track, b: Body, port: Optional[int], dt: float) -> Body:
    (px, py, vx, vy, a, w, qx, qy, ux, uy, roll, rate, x, z,
     heading) = b
    level = tr.level
    grav, soft = level.gravity, level.soft
    steady, damp = level.steady, level.damp
    drive = DRIVE.get(port, 0) * soft
    lean = LEAN.get(port, 0) * soft
    side = SIDE.get(port, 0) * soft
    h = dt / SUB
    for _s in range(SUB):
        dx, dy = qx - px, qy - py
        ln = math.hypot(dx, dy) or 1e-9
        nx, ny = dx / ln, dy / ln
        rel = (ux - vx) * nx + (uy - vy) * ny
        f = -K * (ln - POST) - C * rel
        fqx, fqy = f * nx, f * ny
        # leaning: a push across the body (forward is clockwise)
        tx, ty = ny, -nx
        fqx += LEAN_F_N * lean * tx
        fqy += LEAN_F_N * lean * ty
        # the training wheels: back toward upright, and the sway damped
        if steady or damp:
            sway = (ux - vx) * tx + (uy - vy) * ty
            hold = MR * (-steady * nx - damp * sway)
            fqx += hold * tx
            fqy += hold * ty
        fpx, fpy = -fqx, -fqy
        # pedalling turns the wheel clockwise and rocks the rider back
        tau = -TORQUE * drive
        if drive and abs(w) > SPIN * soft ** 0.5 and (w < 0) == (tau < 0):
            tau = 0.0
        w += tau / IW * h
        back = -tau / ln
        fqx += back * tx
        fqy += back * ty
        fpx -= back * tx
        fpy -= back * ty
        ux += fqx / MR * h
        uy += (fqy / MR - grav) * h
        vx += fpx / MW * h
        vy += (fpy / MW - grav) * h
        w *= 1 - 0.3 * h
        # a sideways lean turns the wheel; the turn's swing outward
        # holds the lean up a little, never all the way
        speed = vx
        turning = speed * math.tan(max(-1.2, min(1.2, roll))) / TURN
        outward = min(speed * speed / TURN, 0.7 * grav)
        rate += ((grav - outward - steady) / SIDE_H * math.sin(roll)
                 + SIDE_A * side - (0.3 + damp) * rate) * h
        roll += rate * h
        heading += turning * h
        px, py = px + vx * h, py + vy * h
        qx, qy = qx + ux * h, qy + uy * h
        a += w * h
        here = Body(px, py, vx, vy, a, w, qx, qy, ux, uy, roll, rate, x, z,
                    heading)
        px, py, vx, vy, w = _contact(tr, here, px, py, vx, vy, w, h, grav)
        # keep the axle at nought: move the plane along instead
        x += px * math.cos(heading)
        z += px * math.sin(heading)
        qx -= px
        px = 0.0
    if abs(roll) > math.pi / 2:          # lying on the ground
        roll, rate = math.copysign(math.pi / 2, roll), 0.0
    return Body(px, py, vx, vy, a, w, qx, qy, ux, uy, roll, rate, x, z,
                heading)


def frame(b: Body):
    """The heading, the rider's right, and up, as world vectors."""
    c, s = math.cos(b.heading), math.sin(b.heading)
    return (c, 0.0, s), (-s, 0.0, c), (0.0, 1.0, 0.0)


def point(tr: Track, b: Body, share: float) -> Tuple[float, float, float]:
    """A point a *share* of the way out along the body from the axle (1
    is the seat, HEAD the head), in the world, tipped sideways with the
    whole unicycle about where the wheel stands."""
    f, r, _up = frame(b)
    floor = height(tr, b.x, b.z)
    ahead = b.px + (b.qx - b.px) * share
    tall = b.py - floor + (b.qy - b.py) * share
    side = tall * math.sin(b.roll)
    return (b.x + f[0] * ahead + r[0] * side,
            floor + tall * math.cos(b.roll),
            b.z + f[2] * ahead + r[2] * side)


def head(tr: Track, b: Body) -> Tuple[float, float, float]:
    return point(tr, b, HEAD)


def tilt(b: Body) -> float:
    """The rider's lean from upright along the heading: forward is
    positive."""
    return math.atan2(b.qx - b.px, b.qy - b.py)


def crashed(tr: Track, b: Body) -> Optional[str]:
    hx, hy, hz = head(tr, b)
    if hy - height(tr, hx, hz) < 0.15:
        return _('Head over heels') if abs(b.roll) < 1.0 else \
            _('Toppled over sideways')
    return None


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Track:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(60):
        flags = _route(level, draw)
        x0, z0, nx, nz, heights = _ground(level, flags, draw)
        tr = Track(level, tuple(flags), x0, z0, nx, nz, heights, 900.0, 0.0)
        ok, _m, t = ride(tr)
        if not ok:
            continue
        tr = tr._replace(seconds=t * level.slack + 3.0, best=t)
        if play(tr)[0]:
            return tr
    raise RuntimeError('unicycle: no field for rung %d' % rung)


class Run(object):
    def __init__(self, tr: Track) -> None:
        self.tr = tr
        self.level = tr.level
        self.t = 0.0
        self.body = begin(tr)
        self.flag = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = tr.seconds
        self.last = None

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        port = control if isinstance(control, int) else None
        self.last = port
        self.body = advance(self.tr, self.body, port, dt)
        why = crashed(self.tr, self.body)
        if why:
            self.result = (False, why)
            self._note(0.5, 90.0, 2, 0.5)
            return
        fx, fz = self.tr.flags[self.flag]
        if math.hypot(self.body.x - fx, self.body.z - fz) < REACH:
            self.flag += 1
            if self.flag == len(self.tr.flags):
                self.result = (True, _('At the last flag in %.1f s')
                               % self.t)
                self._note(0.3, 1320.0, 1, 0.3)
                return
            self._note(0.2, 990.0, 1, 0.3)
        if self.t > self.tr.seconds:
            fx, fz = self.tr.flags[self.flag]
            self.result = (False, _('Out of time, %.0f m to the flag') %
                           math.hypot(self.body.x - fx, self.body.z - fz))


def act(run: Run, port: int) -> None:
    pass


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def steer(tr: Track, b: Body, flag: int = 0) -> Optional[int]:
    """Balance by leaning, and pedal toward a cruising speed: lean so
    the body stands a little ahead of upright when speeding up; lean
    sideways against a topple, and into the turn towards the flag."""
    v = b.ux                             # the body's speed: steadier
    fx, fz = tr.flags[min(flag, len(tr.flags) - 1)]
    off = _wrap(math.atan2(fz - b.z, fx - b.x) - b.heading)
    far = math.hypot(fx - b.x, fz - b.z)
    want = 2.2 * math.sqrt(tr.level.soft) ** 0.5
    if any(along(tr, b, d) < along(tr, b, 0.0) - 0.3
           for d in (0.5, 1.0, 1.5)):
        want *= 0.65                     # a ledge ahead: go gently
    if abs(off) > 0.6 or far < 3.0:
        want *= 0.7                      # a sharp turn: slow for it
    th = tilt(b)
    # the body's own swing: across the body, relative to the wheel
    dx, dy = b.qx - b.px, b.qy - b.py
    ln = math.hypot(dx, dy) or 1e-9
    rate = ((b.ux - b.vx) * dy - (b.uy - b.vy) * dx) / (ln * ln)
    target = max(-0.25, min(0.25, 0.12 * (want - v)))
    u = 6.0 * (th - target) + 1.2 * rate
    lean = 1 if u < -0.15 else -1 if u > 0.15 else 0
    drive = 1 if v < want - 0.2 else -1 if v > want + 0.3 else 0
    if th < -0.35:
        drive = -1 if drive >= 0 else drive
    if th > 0.35:
        drive = 1
    table = {(0, 0): None, (1, 0): PEDAL, (-1, 0): BACK, (0, -1): LEAN_B,
             (0, 1): LEAN_F, (1, -1): PEDAL_B, (1, 1): PEDAL_F,
             (-1, -1): BACK_B, (-1, 1): BACK_F}
    # sideways: lean into the turn the flag needs, and against a topple
    want_roll = max(-0.14, min(0.14, 0.5 * off)) if v > 0.3 else 0.0
    s = 4.0 * (b.roll - want_roll) + 1.6 * b.rate
    if abs(s) > 0.06 and (abs(s) > 0.25 or lean == 0):
        return LEAN_L if s > 0 else LEAN_R
    return table[(drive, lean)]


def ride(tr: Track, dt: float = 1 / 30.0) -> Tuple[bool, str, float]:
    run = Run(tr)
    while run.result is None:
        run.step(dt, steer(tr, run.body, run.flag))
    return run.result[0], run.result[1], run.t


def autopilot(run: Run) -> List[int]:
    if run.result is not None:
        return []
    p = steer(run.tr, run.body, run.flag)
    return [] if p is None else [p]


def play(tr: Track, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(tr)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
