# -*- coding: utf-8 -*-
"""Balance: carry a pole upright on a cart from flag to flag.

A cart runs on a flat square yard with a pole hinged on top that can
lean any way. Push the cart left, right, away or near; the pole leans
the other way and falls unless the cart gets back under it. To move
right you must first let the pole lean right -- which means nudging
left -- and the same away and near. Each flag is collected by standing
the cart still under it, pole up, for a second.

The ladder:

* rungs 1-8: soft gravity and gentle pushes, and training wheels: a
  pull back to upright and a damper on the pole's swing. At rung 1 the
  pole stands itself up again if let go; by rung 3 the pull is weaker
  than gravity, and from rung 8 it is gone. Everything firms up a
  little each rung (full strength from rung 9);
* rungs 1-3: a long, slow pole, two flags close together;
* rungs 4-6: a shorter pole, three flags;
* rungs 7-9: flags far apart;
* rungs 10-12: gusts push the pole;
* rungs 13-15: a short, quick pole;
* rungs 16-19: the pole's length changes partway through, unannounced;
* from rung 20: shorter still, stronger gusts, more flags.

A fall is only the lantern on the pole's top touching the ground. The
yard has a fence: the cart stops against it. The other fail is the time
running out.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

LEFT, RIGHT, AWAY, NEAR = range(4)
PORTS = 4
EVENTS = ()
TRACK = 30.0          # the yard is TRACK by TRACK metres
G = 9.8
PUSH = 12.0           # cart acceleration under a push
ROLL = 0.6            # cart slowing with no push
FENCE = 0.6           # how near the fence the cart's middle can come
HOLD = 1.0            # seconds still at a flag
#: Each port as a push along (x, z): x to the right, z away.
PUSHES = {LEFT: (-1, 0), RIGHT: (1, 0), AWAY: (0, 1), NEAR: (0, -1)}


def gentle(rung: int) -> float:
    """How much the ladder's bottom is softened: 1 at rung 1, falling
    by an eighth a rung, nothing from rung 9."""
    return max(0.0, min(1.0, (9 - int(rung)) / 8.0))


#: Gravity at rung 1: a pole there falls about three times as slowly.
G_SOFT = 1.1


class Grade(NamedTuple):
    rung: int
    length: float
    flags: int
    spread: float
    gusts: float
    changes: bool
    seconds: float
    gravity: float
    push: float
    steady: float = 0.0        # a pull back to upright, like gravity's
    damp: float = 0.1          # how fast the pole's swing dies away


def assist(soft: float) -> float:
    """The training wheels, as a share of gravity: more than gravity on
    rungs 1 and 2 (the pole stands up again by itself), then well under
    it -- never nearly equal, where the pole would neither stand nor
    fall and is hard to read -- and gone from rung 8."""
    rung = round(9 - 8 * soft)
    return {1: 1.3, 2: 1.1, 3: 0.6, 4: 0.45, 5: 0.3, 6: 0.18,
            7: 0.08}.get(rung, 0.0)


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    flags = 2 if r < 4 else 3 if r < 20 else min(6, 4 + top // 4)
    soft = gentle(r)
    return Grade(
        rung=r,
        length=(3.0 if r < 4 else 2.0 if r < 13 else 1.4 if r < 20
                else max(0.9, 1.2 - 0.03 * top)),
        flags=flags,
        spread=6.0 if r < 7 else 14.0,
        gusts=0.0 if r < 10 else (0.6 if r < 20 else 0.8 + 0.04 * top),
        changes=r >= 16,
        seconds=(20.0 + 9.0 * flags) * (1.0 + 1.0 * soft),
        gravity=G * (G_SOFT / G) ** soft,
        push=PUSH * (G_SOFT / G) ** (0.6 * soft),
        steady=G * (G_SOFT / G) ** soft * assist(soft),
        damp=0.1 + 1.2 * soft)


class Course(NamedTuple):
    level: Grade
    flags: List[Tuple[float, float]]
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
    x = z = TRACK / 2
    for _k in range(level.flags):
        for _try in range(80):
            a = draw.uniform(0, 2 * math.pi)
            d = draw.uniform(level.spread * 0.6, level.spread)
            nx, nz = x + d * math.cos(a), z + d * math.sin(a)
            if 3.0 <= nx <= TRACK - 3.0 and 3.0 <= nz <= TRACK - 3.0:
                break
        else:
            nx, nz = TRACK - x, TRACK - z
        flags.append((round(nx, 2), round(nz, 2)))
        x, z = nx, nz
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
        self.x = self.z = TRACK / 2
        self.v = self.w = 0.0            # the cart's speed along x and z
        k = course.gust_seed
        #: The pole's lean towards +x and towards +z, and their rates.
        self.theta = 0.02 if k % 2 else -0.02
        self.phi = 0.015 if k % 4 < 2 else -0.015
        self.omega = self.psi = 0.0
        self.flag = 0
        self.still = 0.0
        self.result: Optional[Tuple[bool, str]] = None
        self.pushing = (0, 0)

    def length(self, t: Optional[float] = None) -> float:
        t = self.t if t is None else t
        out = self.course.lengths[0][1]
        for when, l in self.course.lengths:
            if t >= when:
                out = l
        return out

    def gust(self, t: Optional[float] = None) -> Tuple[float, float]:
        """The wind's push on the pole along x and along z."""
        if not self.level.gusts:
            return 0.0, 0.0
        t = self.t if t is None else t
        k = self.course.gust_seed % 17
        size = self.level.gusts * math.sin(t * 0.8 + k) * \
            math.sin(t * 0.31 + 2 * k)
        a = k * 0.7 + 0.2 * math.sin(t * 0.13)
        return size * math.cos(a), size * math.sin(a)

    def accel_for(self, control: Optional[int]) -> Tuple[float, float]:
        if control in PUSHES:
            px, pz = PUSHES[control]
            return px * self.level.push, pz * self.level.push

        def roll(v):
            return 0.0 if abs(v) < 1e-9 else -math.copysign(ROLL, v)
        return roll(self.v), roll(self.w)

    def tip(self) -> Tuple[float, float, float]:
        """The pole's top relative to its hinge: across, up, away."""
        l = self.length()
        return (l * math.sin(self.theta) * math.cos(self.phi),
                l * math.cos(self.theta) * math.cos(self.phi),
                l * math.sin(self.phi))

    def lean(self) -> float:
        """How far the pole is from upright, in radians."""
        c = math.cos(self.theta) * math.cos(self.phi)
        return math.acos(max(-1.0, min(1.0, c)))

    def step(self, dt: float, control: Optional[int]) -> None:
        if self.result is not None:
            return
        self.t += dt
        ax, az = self.accel_for(control)
        p = PUSHES.get(control, (0, 0))
        self.pushing = p
        bv, bw = self.v, self.w
        self.v += ax * dt
        self.w += az * dt
        if not p[0] and bv * self.v < 0:
            self.v = 0.0
        if not p[1] and bw * self.w < 0:
            self.w = 0.0
        self.x += self.v * dt
        self.z += self.w * dt
        # the fence stops the cart
        lo, hi = FENCE, TRACK - FENCE
        if not lo <= self.x <= hi:
            self.x, self.v = max(lo, min(hi, self.x)), 0.0
        if not lo <= self.z <= hi:
            self.z, self.w = max(lo, min(hi, self.z)), 0.0
        l = self.length()
        g = self.level.gravity - self.level.steady
        damp = self.level.damp
        gx, gz = self.gust()
        alpha = ((g * math.sin(self.theta) - ax * math.cos(self.theta)
                  + gx) / l - damp * self.omega)
        beta = ((g * math.sin(self.phi) - az * math.cos(self.phi)
                 + gz) / l - damp * self.psi)
        self.omega += alpha * dt
        self.theta += self.omega * dt
        self.psi += beta * dt
        self.phi += self.psi * dt
        if math.cos(self.theta) * math.cos(self.phi) <= 0.0:
            self.result = (False, _('The lantern hit the ground'))
            return
        fx, fz = self.course.flags[self.flag]
        if math.hypot(self.x - fx, self.z - fz) < 0.8 and \
                math.hypot(self.v, self.w) < 1.0 and \
                self.lean() < math.radians(12):
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

@lru_cache(maxsize=64)
def gains(l: float, g: float, damp: float = 0.1,
          dt: float = 1 / 60.0) -> Tuple[float, ...]:
    """Regulator gains for one axis (linear quadratic, the cart's
    acceleration as the input), worked out by iterating the discrete
    Riccati equation: a = k0 (x - flag) + k1 v + k2 theta + k3 omega."""
    import numpy as np
    # state (x, v, theta, omega); x'' = a; theta'' = (g theta - a) / l
    A = np.array([[1, dt, 0, 0], [0, 1, 0, 0], [0, 0, 1, dt],
                  [0, 0, g / l * dt, 1 - damp * dt]])
    B = np.array([[0.0], [dt], [0.0], [-dt / l]])
    Q = np.diag([2.0, 0.2, 10.0, 0.5])
    Rw = 0.05
    P = Q.copy()
    for _it in range(200000):
        PB = P @ B
        K = np.linalg.solve(Rw + B.T @ PB, PB.T @ A)
        nP = A.T @ P @ A - A.T @ PB @ K + Q
        if np.max(np.abs(nP - P)) < 1e-7 * max(1.0, np.max(np.abs(P))):
            P = nP
            break
        P = nP
    K = K.ravel()
    # u = -K s; the controller below adds these terms, so turn the sign
    return tuple(-k for k in K)


def autopilot(run: Run) -> List[int]:
    """The regulator's acceleration on both axes, as one on-off push a
    step whose error carries over to the next steps. It knows the pole's
    length only by watching how the pole moves -- here, simply, by being
    told."""
    if run.result is not None:
        return []
    g = run.level.gravity
    k = gains(round(run.length(), 3), round(g - run.level.steady, 4),
              run.level.damp)
    fx, fz = run.course.flags[run.flag]
    gx, gz = run.gust()

    def want(pos, flag, vel, ang, rate, wind):
        err = max(-3.0, min(3.0, pos - flag))
        return (k[0] * err + k[1] * vel + k[2] * (ang + wind / g)
                + k[3] * rate)
    wx = want(run.x, fx, run.v, run.theta, run.omega, gx)
    wz = want(run.z, fz, run.w, run.phi, run.psi, gz)
    ox, oz = getattr(run, 'owed', (0.0, 0.0))
    ox, oz = ox * 0.9 + wx, oz * 0.9 + wz
    best, best_err, best_a = None, None, (0.0, 0.0)
    for port in (None, LEFT, RIGHT, AWAY, NEAR):
        a = run.accel_for(port)
        e = math.hypot(a[0] - ox, a[1] - oz)
        if best_err is None or e < best_err - 1e-9:
            best, best_err, best_a = port, e, a
    run.owed = (ox - best_a[0], oz - best_a[1])
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
