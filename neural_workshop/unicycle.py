# -*- coding: utf-8 -*-
"""Unicycle: ride a wobbling rider on one wheel over the hills to the
flag.

Side on, a rider sits on a unicycle. The rider is joined to the wheel
by a springy body, so every bump shakes them and every pedal stroke
rocks them back. Pedal and back-pedal the wheel; lean the rider forward
and back. If the head touches the ground, or the rider drops into a
pit, the ride is over. Reach the flag in time.

* rung 1: flat ground, a short ride, plenty of time;
* rungs 2-3: gentle hills;
* rungs 4-6: steeper hills and small bumps;
* rungs 7-9: steps up and down;
* rungs 10-12: ledges to ride off, the ground dropping away;
* rungs 13 and up: the ride grows longer and rougher, and the time
  allowed closes in on what the best ride takes, without end.

For the agent boundary: ports 0-1 pedal and back-pedal; 2-3 lean back
and forward; 4-7 pedal or back-pedal while leaning back or forward --
each for the step it is sent in.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

(PEDAL, BACK, LEAN_B, LEAN_F, PEDAL_B, PEDAL_F, BACK_B, BACK_F) = range(8)
PORTS = 8
EVENTS = ()
DRIVE = {PEDAL: 1, BACK: -1, PEDAL_B: 1, PEDAL_F: 1, BACK_B: -1, BACK_F: -1}
LEAN = {LEAN_B: -1, LEAN_F: 1, PEDAL_B: -1, PEDAL_F: 1, BACK_B: -1,
        BACK_F: 1}
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
GRIP = 1.2
SUB = 4
PATCHES = ('wood', 'bell', 'growl')


class Grade(NamedTuple):
    rung: int
    length: float
    hills: float               # the swell's height
    bumps: float               # small bumps' height
    steps: float               # steps' height, or 0
    pits: int
    slack: float               # time allowed over the reference's


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, 22.0, 0.0, 0.0, 0.0, 0, 3.0)
    if r < 4:
        return Grade(r, 30.0, 0.5 + 0.3 * (r - 2), 0.0, 0.0, 0, 2.5)
    if r < 7:
        return Grade(r, 40.0, 1.2 + 0.2 * (r - 4), 0.06 + 0.02 * (r - 4),
                     0.0, 0, 2.2)
    if r < 10:
        return Grade(r, 45.0, 1.4, 0.08, 0.15 + 0.05 * (r - 7), 0, 2.0)
    if r < 13:
        return Grade(r, 50.0, 1.4, 0.08, 0.2, 1 + (r - 10) // 2, 1.8)
    return Grade(r, min(140.0, 55.0 + 3.0 * (r - 13)),
                 min(3.0, 1.5 + 0.05 * (r - 13)),
                 min(0.16, 0.09 + 0.004 * (r - 13)),
                 min(0.3, 0.2 + 0.005 * (r - 13)), 2 + (r - 13) // 6,
                 max(1.08, 1.1 + 0.6 * 0.9 ** (r - 13)))


class Track(NamedTuple):
    level: Grade
    xs: Tuple[float, ...]
    ys: Tuple[float, ...]
    finish: float
    seconds: float
    best: float                     # the reference's time


DX = 0.25


def ground(tr: Track, x: float) -> float:
    i = int((x - tr.xs[0]) / DX)
    i = max(0, min(len(tr.xs) - 2, i))
    u = (x - tr.xs[i]) / DX
    return tr.ys[i] + (tr.ys[i + 1] - tr.ys[i]) * u


def _shape(level: Grade, draw) -> Tuple[List[float], List[float], float]:
    start, end = -4.0, level.length + 6.0
    n = int((end - start) / DX) + 1
    xs = [start + i * DX for i in range(n)]
    waves = [(level.hills * draw.uniform(0.3, 0.6), draw.uniform(0.12, 0.3),
              draw.uniform(0, 6.3)) for _w in range(2)] if level.hills else []
    ys = []
    for x in xs:
        t = max(0.0, x - 3.0)
        ease = min(1.0, t / 4.0)
        ys.append(ease * sum(a * (math.sin(k * t + ph) - math.sin(ph))
                             for a, k, ph in waves))
    # bumps
    if level.bumps:
        x = 6.0
        while x < level.length:
            x += draw.uniform(2.0, 5.0)
            h = level.bumps * draw.uniform(0.6, 1.0)
            for i, px in enumerate(xs):
                d = abs(px - x)
                if d < 0.4:
                    ys[i] += h * (1 - d / 0.4)
    # steps: the ground shifts up or down from here on
    if level.steps:
        x = 8.0
        while x < level.length - 4:
            x += draw.uniform(5.0, 9.0)
            h = level.steps * draw.uniform(0.6, 1.0) * draw.choice((-1, 1))
            for i, px in enumerate(xs):
                if px >= x:
                    ys[i] += h * min(1.0, (px - x) / 0.75)
    # ledges: the ground drops away, to be ridden off
    if level.pits:
        span = (level.length - 14) / level.pits
        for k in range(level.pits):
            x = 10.0 + span * (k + draw.uniform(0.35, 0.65))
            h = draw.uniform(0.5, 0.8) + 0.03 * max(0, level.rung - 13)
            h = min(1.4, h)
            for i, px in enumerate(xs):
                if px >= x:
                    ys[i] -= h * min(1.0, (px - x) / 0.25)
    return xs, ys, level.length


class Body(NamedTuple):
    px: float
    py: float
    vx: float
    vy: float
    a: float                        # the wheel's turn
    w: float                        # its spin, anticlockwise
    qx: float
    qy: float
    ux: float
    uy: float


def begin(tr: Track) -> Body:
    y = ground(tr, 0.0) + R
    # never quite upright: left alone, the rider tips forward
    lean = 0.03
    return Body(0.0, y, 0.0, 0.0, 0.0, 0.0, POST * math.sin(lean),
                y + POST * math.cos(lean), 0.0, 0.0)


def _contact(tr: Track, px, py, vx, vy, w, dt):
    """The wheel against the ground: pushed out, its fall stopped, and
    rolling with grip."""
    best = None
    i0 = int((px - R - 0.3 - tr.xs[0]) / DX)
    for i in range(max(0, i0), min(len(tr.xs) - 1, i0 + int(
            (2 * R + 0.6) / DX) + 2)):
        ax, ay, bx, by = tr.xs[i], tr.ys[i], tr.xs[i + 1], tr.ys[i + 1]
        ex, ey = bx - ax, by - ay
        u = max(0.0, min(1.0, ((px - ax) * ex + (py - ay) * ey) /
                         (ex * ex + ey * ey)))
        cx, cy = ax + ex * u, ay + ey * u
        d = math.hypot(px - cx, py - cy)
        if d < R and (best is None or d < best[0]):
            best = (d, cx, cy)
    if best is None:
        return px, py, vx, vy, w, False
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
    cap = GRIP * (jn + MW * GRAV * dt)
    jt = max(-cap, min(cap, jt))
    vx += jt / MW * tx
    vy += jt / MW * ty
    w += jt * R / IW
    return px, py, vx, vy, w, True


def advance(tr: Track, b: Body, port: Optional[int], dt: float) -> Body:
    px, py, vx, vy, a, w, qx, qy, ux, uy = b
    drive = DRIVE.get(port, 0)
    lean = LEAN.get(port, 0)
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
        fpx, fpy = -fqx, -fqy
        # pedalling turns the wheel clockwise and rocks the rider back
        tau = -TORQUE * drive
        if drive and abs(w) > SPIN and (w < 0) == (tau < 0):
            tau = 0.0
        w += tau / IW * h
        back = -tau / ln
        fqx += back * -tx * -1.0
        fqy += back * -ty * -1.0
        fpx -= back * -tx * -1.0
        fpy -= back * -ty * -1.0
        ux += fqx / MR * h
        uy += (fqy / MR - GRAV) * h
        vx += fpx / MW * h
        vy += (fpy / MW - GRAV) * h
        w *= 1 - 0.3 * h
        px, py = px + vx * h, py + vy * h
        qx, qy = qx + ux * h, qy + uy * h
        a += w * h
        px, py, vx, vy, w, _on = _contact(tr, px, py, vx, vy, w, h)
    return Body(px, py, vx, vy, a, w, qx, qy, ux, uy)


def head(b: Body) -> Tuple[float, float]:
    return b.px + (b.qx - b.px) * HEAD, b.py + (b.qy - b.py) * HEAD


def tilt(b: Body) -> float:
    """The rider's lean from upright: forward is positive."""
    return math.atan2(b.qx - b.px, b.qy - b.py)


def crashed(tr: Track, b: Body) -> Optional[str]:
    hx, hy = head(b)
    if hy - ground(tr, hx) < 0.15:
        return _('Head over heels')
    if b.qy - ground(tr, b.qx) < 0.1:
        return _('Fell off')
    return None


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Track:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(100):
        xs, ys, finish = _shape(level, draw)
        tr = Track(level, tuple(xs), tuple(ys), finish, 600.0, 0.0)
        ok, _m, t = ride(tr)
        if not ok:
            continue
        tr = tr._replace(seconds=t * level.slack + 2.0, best=t)
        if play(tr)[0]:
            return tr
    raise RuntimeError('unicycle: no track for rung %d' % rung)


class Run(object):
    def __init__(self, tr: Track) -> None:
        self.tr = tr
        self.level = tr.level
        self.t = 0.0
        self.body = begin(tr)
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
        if self.body.px >= self.tr.finish:
            self.result = (True, _('At the flag in %.1f s') % self.t)
            self._note(0.3, 1320.0, 1, 0.3)
            return
        if self.t > self.tr.seconds:
            self.result = (False, _('Out of time, %.0f m to go') % (
                self.tr.finish - self.body.px))


def act(run: Run, port: int) -> None:
    pass


def steer(tr: Track, b: Body) -> Optional[int]:
    """Balance by leaning, and pedal toward a cruising speed: lean so
    the body stands a little ahead of upright when speeding up."""
    v = b.ux                             # the body's speed: steadier
    want = 2.2
    here = ground(tr, b.px)
    if any(ground(tr, b.px + d) < here - 0.3 for d in (0.5, 1.0, 1.5)):
        want = 1.4                       # a ledge ahead: go gently
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
    return table[(drive, lean)]


def ride(tr: Track, dt: float = 1 / 30.0) -> Tuple[bool, str, float]:
    run = Run(tr)
    while run.result is None:
        run.step(dt, steer(tr, run.body))
    return run.result[0], run.result[1], run.t


def autopilot(run: Run) -> List[int]:
    if run.result is not None:
        return []
    p = steer(run.tr, run.body)
    return [] if p is None else [p]


def play(tr: Track, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(tr)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
