# -*- coding: utf-8 -*-
"""Shadow Play: turn a thing in the lamplight until its shadow fits.

A bent rod -- a few straight lengths joined at right angles, wandering
through all three dimensions -- hangs in front of a wall with a lamp
shining past it. Its shadow falls on the wall, and on the wall a
glowing outline shows the shadow wanted. Turn the rod -- drag it with
the mouse, or the arrow keys (A and D, W and S, Q and E) -- until its
shadow lies in the outline, and hold it there for a moment.

Turning a thing in the head and seeing what it throws is easy to feel
and hard to say: every control turns the whole rod, so every part of the
shadow moves at once, and the shadow the outline wants can be thrown by
more than one way the rod might hang.

The ladder:

* rungs 1-3: a short rod turning about one upright axis; a hum rises as
  the shadow comes close;
* rungs 4-6: a longer rod, tipping forward and back as well;
* rungs 7-9: rolling too, longer rods;
* rungs 10-12: a second lamp throws a shadow on the floor, which must
  fit its own outline too; no hum;
* rungs 13-15: the outline turns slowly: catch it and keep up with it;
* rungs 16-19: the lamp swings to and fro, so the shadow wanted keeps
  changing with it;
* from rung 20: all of it, longer rods, a tighter fit every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Sequence, Set, Tuple

from .drshape import Note
from .i18n import _

YAW_L, YAW_R, PITCH_D, PITCH_U, ROLL_L, ROLL_R = range(6)
PORTS = 6
EVENTS = ()
SPIN = math.radians(60.0)      # turning speed, radians a second
WALL = 3.0                     # the wall stands at z = -WALL
FLOOR = 2.2                    # the floor lies at y = -FLOOR
CHECK = 1 / 20.0               # how often the fit is measured

Vec = Tuple[float, float, float]
Mat = Tuple[Vec, Vec, Vec]
Seg = Tuple[Vec, Vec]


class Grade(NamedTuple):
    rung: int
    bends: int
    axes: int                  # 1 yaw, 2 and pitch, 3 and roll
    tol: float
    hum: bool
    floor: bool
    turning: float             # the outline's turn, radians a second
    swing: float               # the lamp's swing, radians
    hold: float
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        bends=(3 if r < 4 else 4 if r < 7 else 5 if r < 20
               else min(8, 6 + top // 3)),
        axes=1 if r < 4 else 2 if r < 7 else 3,
        tol=(0.10 if r < 4 else 0.08 if r < 10 else 0.07 if r < 20
             else max(0.045, 0.065 - 0.002 * top)),
        hum=r < 10,
        floor=10 <= r < 13 or r >= 20,
        turning=(math.radians(10.0) if 13 <= r < 16 else
                 math.radians(min(18.0, 10.0 + top)) if r >= 20 else 0.0),
        swing=math.radians(22.0) if r >= 16 else 0.0,
        hold=0.6 if r < 13 else 1.0,
        seconds=30.0 if r < 4 else 40.0 if r < 7 else 55.0 if r < 20
        else 50.0)


# --- small linear algebra ---------------------------------------------------

def mat(axis: int, a: float) -> Mat:
    c, s = math.cos(a), math.sin(a)
    if axis == 0:          # about x: pitch
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 1:          # about y: yaw
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def mul(a: Mat, b: Mat) -> Mat:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                       for j in range(3)) for i in range(3))


def tr(a: Mat) -> Mat:
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))


def app(m: Mat, v: Vec) -> Vec:
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def angle_between(a: Mat, b: Mat) -> float:
    q = mul(a, tr(b))
    c = (q[0][0] + q[1][1] + q[2][2] - 1) / 2
    return math.acos(max(-1.0, min(1.0, c)))


def _norm(v: Vec) -> Vec:
    d = math.sqrt(sum(x * x for x in v)) or 1.0
    return tuple(x / d for x in v)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def random_turn(draw: random.Random) -> Mat:
    m = mat(1, draw.uniform(-math.pi, math.pi))
    m = mul(mat(0, draw.uniform(-math.pi, math.pi)), m)
    return mul(mat(2, draw.uniform(-math.pi, math.pi)), m)


# --- the rod ---------------------------------------------------------------------

STEPS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def make_rod(bends: int, draw: random.Random) -> List[Seg]:
    """A path of *bends* + 1 straight lengths at right angles that uses
    all three directions and never comes back on itself, centred and
    scaled to about a unit across."""
    while True:
        p = (0, 0, 0)
        seen = {p}
        pts = [p]
        last = None
        ok = True
        for _k in range(bends + 1):
            choices = [s for s in STEPS if last is None or
                       (_dot(s, last) == 0)]
            draw.shuffle(choices)
            for s in choices:
                n = draw.choice((1, 1, 2))
                path = [tuple(p[i] + s[i] * j for i in range(3))
                        for j in range(1, n + 1)]
                if not any(q in seen for q in path):
                    seen.update(path)
                    p = path[-1]
                    pts.append(p)
                    last = s
                    break
            else:
                ok = False
                break
        if not ok:
            continue
        dirs = {tuple(abs(b[i] - a[i]) > 0 for i in range(3))
                for a, b in zip(pts, pts[1:])}
        if len(dirs) < 3:
            continue
        c = tuple(sum(q[i] for q in pts) / len(pts) for i in range(3))
        span = max(max(abs(q[i] - c[i]) for i in range(3)) for q in pts)
        k = 1.0 / max(span, 1.0)
        pts = [tuple((q[i] - c[i]) * k for i in range(3)) for q in pts]
        return list(zip(pts, pts[1:]))


def samples(rod: Sequence[Seg], each: int = 6) -> List[Vec]:
    out = []
    for a, b in rod:
        for j in range(each):
            f = j / each
            out.append(tuple(a[i] + (b[i] - a[i]) * f for i in range(3)))
    out.append(rod[-1][1])
    return out


# --- the lamps --------------------------------------------------------------------

BACK = _norm((0.30, -0.18, -1.0))     # the wall lamp's light
DOWN = _norm((0.12, -1.0, -0.25))     # the floor lamp's light


def wall_light(swing: float, t: float) -> Vec:
    if not swing:
        return BACK
    a = swing * math.sin(0.35 * t)
    return _norm(app(mat(1, a), BACK))


def on_wall(p: Vec, light: Vec) -> Vec:
    s = (-WALL - p[2]) / light[2]
    return (p[0] + light[0] * s, p[1] + light[1] * s, -WALL)


def on_floor(p: Vec, light: Vec = DOWN) -> Vec:
    s = (-FLOOR - p[1]) / light[1]
    return (p[0] + light[0] * s, -FLOOR, p[2] + light[2] * s)


def shadow(points: Sequence[Vec], light: Vec, floor: bool = False
           ) -> List[Tuple[float, float]]:
    if floor:
        return [(q[0], q[2]) for q in (on_floor(p, light) for p in points)]
    return [(q[0], q[1]) for q in (on_wall(p, light) for p in points)]


def chamfer(a: Sequence[Tuple[float, float]],
            b: Sequence[Tuple[float, float]]) -> float:
    def one(xs, ys):
        total = 0.0
        sqrt = math.sqrt
        for x, y in xs:
            best = 1e18
            for u, v in ys:
                d = (x - u) * (x - u) + (y - v) * (y - v)
                if d < best:
                    best = d
            total += sqrt(best)
        return total / len(xs)
    return max(one(a, b), one(b, a))


# --- the trial ---------------------------------------------------------------------

class Setup(NamedTuple):
    level: Grade
    rod: List[Seg]
    target: Mat                # how the rod must hang, at t = 0
    start: Mat


def target_at(setup: Setup, t: float) -> Mat:
    if not setup.level.turning:
        return setup.target
    return mul(mat(1, setup.level.turning * t), setup.target)


def misfit(setup: Setup, turn: Mat, t: float,
           pts: Optional[List[Vec]] = None) -> float:
    """How far the rod's shadows (turned *turn*) are from the outlines."""
    pts = pts or samples(setup.rod)
    want = target_at(setup, t)
    light = wall_light(setup.level.swing, t)
    mine = [app(turn, p) for p in pts]
    goal = [app(want, p) for p in pts]
    m = chamfer(shadow(mine, light), shadow(goal, light))
    if setup.level.floor:
        m = max(m, chamfer(shadow(mine, DOWN, True),
                           shadow(goal, DOWN, True)))
    return m


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Setup:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(40):
        setup = _build(level, draw)
        if setup is None:
            continue
        best = best or setup
        if play(setup)[0]:
            return setup
    return best


def _build(level: Grade, draw: random.Random) -> Optional[Setup]:
    rod = make_rod(level.bends, draw)
    base = random_turn(draw)
    if level.axes == 1:
        target = mul(mat(1, draw.uniform(-math.pi, math.pi)), base)
        off = draw.uniform(math.radians(70), math.radians(150))
        start = mul(mat(1, off * draw.choice((-1, 1))), target)
    else:
        target = base
        start = random_turn(draw)
        if angle_between(start, target) < math.radians(80):
            return None
    setup = Setup(level, rod, target, start)
    if misfit(setup, start, 0.0) < 4 * level.tol:
        return None
    return setup


def _on(control) -> Set[int]:
    if control is None:
        return set()
    if isinstance(control, int):
        return {control}
    return set(control)


AXIS_OF = {YAW_L: (1, -1), YAW_R: (1, 1), PITCH_D: (0, 1), PITCH_U: (0, -1),
           ROLL_L: (2, 1), ROLL_R: (2, -1)}


class Run:
    def __init__(self, setup: Setup) -> None:
        self.setup = setup
        self.level = setup.level
        self.t = 0.0
        self.turn = setup.start
        self.pts = samples(setup.rod)
        self.fit = misfit(setup, self.turn, 0.0, self.pts)
        self.checked = 0.0
        self.fit_since: Optional[float] = None
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.next_hum = 0.3
        self.seed = 0
        self.dirty = False

    def allowed(self, axis: int) -> bool:
        return {1: 1, 0: 2, 2: 3}[axis] <= self.level.axes

    def rotate(self, axis: int, a: float) -> None:
        """Turn the rod by *a* radians about a world axis (if that axis is
        open at this rung)."""
        if self.result is not None or not self.allowed(axis) or not a:
            return
        self.turn = mul(mat(axis, a), self.turn)
        self.dirty = True

    def close(self) -> float:
        """How near the fit is, 0 (far) to 1 (in the outline)."""
        return max(0.0, min(1.0, 1.0 - (self.fit - self.level.tol)
                            / (5 * self.level.tol)))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        for port in _on(control):
            if port in AXIS_OF:
                axis, sign = AXIS_OF[port]
                self.rotate(axis, sign * SPIN * dt)
        if self.t - self.checked >= CHECK - 1e-9:
            self.checked = self.t
            self.dirty = False
            self.fit = misfit(self.setup, self.turn, self.t, self.pts)
        if self.fit <= self.level.tol:
            if self.fit_since is None:
                self.fit_since = self.t
                self._chime()
            elif self.t - self.fit_since >= self.level.hold:
                self.result = (True, _('The shadow fits'))
                return
        else:
            self.fit_since = None
        if self.level.hum and self.t >= self.next_hum:
            f = 196.0 * 2 ** (1.5 * self.close())
            self.seed += 1
            self.notes.append(Note(self.next_hum, 0.18, f, 0.0, 0.0, 0.22,
                                   0.22, 0.6, 0, self.seed, -1, 0.0))
            self.next_hum += 0.2
        if self.t >= self.level.seconds:
            self.result = (False, _('Out of time'))

    def _chime(self) -> None:
        self.seed += 1
        for k, f in enumerate((660.0, 990.0)):
            self.notes.append(Note(self.t + 0.06 * k, 0.25, f, 0.0, 0.0,
                                   0.3, 0.3, 0.9, 1, self.seed + k, -1, 0.0))


def act(run: Run, port: int) -> None:
    pass


def plan(q: Mat) -> Tuple[float, float, float]:
    """Angles (a, b, c) with q = yaw(a) pitch(b) yaw(c), the shortest."""
    b = math.acos(max(-1.0, min(1.0, q[1][1])))
    if abs(math.sin(b)) < 1e-6:
        return math.atan2(q[0][2], q[0][0]), 0.0, 0.0
    c = math.atan2(q[1][0], -q[1][2])
    a = math.atan2(q[0][1], q[2][1])

    def wrap(x):
        return (x + math.pi) % (2 * math.pi) - math.pi
    alt = (wrap(a + math.pi), -b, wrap(c + math.pi))
    return min(((a, b, c), alt), key=lambda v: sum(abs(x) for x in v))


def autopilot(run: Run) -> List[int]:
    """Turn the rod the shortest way to how it must hang: first about the
    upright, then tipping, then about the upright again."""
    want = target_at(run.setup, run.t)
    q = mul(want, tr(run.turn))
    eps = math.radians(0.6)
    if run.level.axes == 1:
        a = math.atan2(q[0][2], q[0][0])
        if abs(a) < eps:
            return []
        return [YAW_R if a > 0 else YAW_L]
    a, b, c = plan(q)
    if abs(b) <= eps:
        # Barely any tipping left: one turn about the upright does it.
        a = math.atan2(q[0][2], q[0][0])
        if abs(a) <= eps:
            return []
        return [YAW_R if a > 0 else YAW_L]
    if abs(c) > eps:
        return [YAW_R if c > 0 else YAW_L]
    if abs(b) > eps:
        return [PITCH_D if b > 0 else PITCH_U]
    if abs(a) > eps:
        return [YAW_R if a > 0 else YAW_L]
    return []


def play(setup: Setup, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(setup)
    while run.result is None:
        run.step(dt, pilot(run))
    return run.result
