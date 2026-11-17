# -*- coding: utf-8 -*-
"""Rover: drive a rover on another world, where every signal is late.

What you send reaches the rover some time later, and what its camera
sees reaches you some time later again: half the delay each way. Drive
it to each flag in turn without hitting a rock, and without tipping it
over on a slope. On the screen is the rover as it was, not as it is.

* rung 1: a fifth of a second of delay; one flag ahead on open ground;
* rungs 2-3: half a second; two flags, a turn between them;
* rungs 4-6: a second; rocks;
* rungs 7-9: one and a half to two seconds; slopes that tip the rover
  if it drives across them too steeply;
* rungs 10-12: two and a half to three seconds, and the delay itself
  wanders;
* rungs 13 and up: the delay grows by three tenths of a second every
  rung without end; more rocks; the rover rolls on further when let go.

For the agent boundary: ports 0-3 drive, brake (and back up), and
steer left and right, for as long as the step they are sent in --
applied when the signal arrives.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

DRIVE, BRAKE, LEFT, RIGHT = range(4)
PORTS = 4
EVENTS = ()
PUSH = 1.6                     # metres a second, a second
TOP = 3.0                      # metres a second
STEER = 0.55                   # radians a second, per metre a second
FLAG = 2.2                     # how near a flag counts
BODY = 0.9
PATCHES = ('wood', 'bell', 'growl')


class Grade(NamedTuple):
    rung: int
    delay: float
    wander: float              # share the delay wanders by
    flags: int
    rocks: int
    hills: float               # height of the ground's swell
    tip: float                 # the steepest side slope it stands, or 0
    drag: float                # how fast it slows when let go


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, 0.2, 0.0, 1, 0, 0.0, 0.0, 0.8)
    if r < 4:
        return Grade(r, 0.5, 0.0, 2, 0, 0.0, 0.0, 0.8)
    if r < 7:
        return Grade(r, 1.0, 0.0, 3, 8 + 2 * (r - 4), 0.0, 0.0, 0.7)
    if r < 10:
        return Grade(r, 1.5 + 0.25 * (r - 7), 0.0, 3, 12, 2.5, 0.35, 0.6)
    if r < 13:
        return Grade(r, 2.5 + 0.25 * (r - 10), 0.3, 4, 14, 3.0, 0.32, 0.5)
    return Grade(r, 3.0 + 0.3 * (r - 13), 0.3, 4, min(40, 16 + (r - 13)),
                 3.0, 0.3, max(0.2, 0.5 - 0.02 * (r - 13)))


class Ground(NamedTuple):
    level: Grade
    waves: Tuple[Tuple[float, float, float, float], ...]   # amp, kx, kz, ph
    rocks: Tuple[Tuple[float, float, float], ...]          # x, z, radius
    flags: Tuple[Tuple[float, float], ...]
    delays: Tuple[float, ...]       # the delay, second by second
    seconds: float


def height(g: Ground, x: float, z: float) -> float:
    return sum(a * math.sin(kx * x + kz * z + ph) for a, kx, kz, ph in g.waves)


def slope(g: Ground, x: float, z: float, heading: float) -> float:
    """How steeply the ground falls across a rover heading this way."""
    e = 0.5
    sx = (height(g, x + e, z) - height(g, x - e, z)) / (2 * e)
    sz = (height(g, x, z + e) - height(g, x, z - e)) / (2 * e)
    # across: the right-hand direction
    rx, rz = math.cos(heading), -math.sin(heading)
    return abs(sx * rx + sz * rz)


def delay_at(g: Ground, t: float) -> float:
    k = min(len(g.delays) - 1, max(0, int(t)))
    return g.delays[k]


class State(NamedTuple):
    x: float
    z: float
    heading: float
    v: float


def active(queue, t0: float, t1: float) -> dict:
    """How much of the span from *t0* to *t1* each port is held for: a
    command holds from when it lands for as long as the step that sent
    it, so the same commands do the same work however finely time is
    cut."""
    on: dict = {}
    span = t1 - t0
    for at, port, dur in queue:
        lap = min(t1, at + dur) - max(t0, at)
        if lap > 0:
            on[port] = min(1.0, on.get(port, 0.0) + lap / span)
    return on


def advance(g: Ground, s: State, on, dt: float) -> State:
    """One step under the ports held, each for its share of the step."""
    lv = g.level
    if not isinstance(on, dict):
        on = {p: 1.0 for p in on}
    drive, brake = on.get(DRIVE, 0.0), on.get(BRAKE, 0.0)
    v = s.v + PUSH * dt * drive - 2 * PUSH * dt * brake
    coast = max(0.0, 1.0 - drive - brake)
    v -= math.copysign(min(abs(v), lv.drag * dt * coast), v)
    v = max(-1.0, min(TOP, v))
    turn = STEER * max(-1.5, min(1.5, v)) * dt * (
        on.get(RIGHT, 0.0) - on.get(LEFT, 0.0))
    h = s.heading + turn
    return State(s.x + math.sin(h) * v * dt, s.z + math.cos(h) * v * dt, h, v)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Ground:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(60):
        waves = tuple((level.hills * draw.uniform(0.3, 0.6),
                       draw.uniform(-0.15, 0.15), draw.uniform(-0.15, 0.15),
                       draw.uniform(0, 6.3)) for _w in range(3)) \
            if level.hills else ()
        flags = []
        x, z, h = 0.0, 0.0, 0.0
        for k in range(level.flags):
            h += draw.uniform(-1.0, 1.0) if k else draw.uniform(-0.3, 0.3)
            d = draw.uniform(18, 28)
            x, z = x + math.sin(h) * d, z + math.cos(h) * d
            flags.append((x, z))
        rocks = []
        pts = [(0.0, 0.0)] + flags
        while len(rocks) < level.rocks:
            a, b = draw.randrange(len(pts) - 1), draw.random()
            (ax, az), (bx, bz) = pts[a], pts[a + 1]
            rx = ax + (bx - ax) * b + draw.uniform(-4, 4)
            rz = az + (bz - az) * b + draw.uniform(-4, 4)
            if all(math.hypot(rx - fx, rz - fz) > FLAG + 2 for fx, fz in pts):
                rocks.append((rx, rz, draw.uniform(0.6, 1.3)))
        seconds = 30.0 + sum(math.hypot(bx - ax, bz - az) for (ax, az), (bx, bz)
                             in zip(pts, pts[1:])) * (1.0 + 0.5 * level.delay)
        delays = tuple(level.delay * (1 + level.wander * draw.uniform(-1, 1))
                       for _s in range(int(seconds) + 2))
        g = Ground(level, waves, tuple(rocks), tuple(flags), delays, seconds)
        if play(g)[0] and not play(g, lambda run: [DRIVE])[0]:
            return g
    raise RuntimeError('rover: no ground for rung %d' % rung)


class Run(object):
    def __init__(self, g: Ground) -> None:
        self.g = g
        self.level = g.level
        self.t = 0.0
        self.state = State(0.0, 0.0, 0.0, 0.0)
        # (lands, port, how long it holds)
        self.queue: List[Tuple[float, int, float]] = []
        self.history: List[Tuple[float, State]] = [(0.0, self.state)]
        self.reached = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = g.seconds

    def send(self, port: Optional[int], dur: float) -> None:
        if port is not None:
            up = delay_at(self.g, self.t) / 2
            self.queue.append((self.t + up, port, dur))

    def seen(self) -> State:
        """The rover as the screen shows it: as it was half a delay ago."""
        back = self.t - delay_at(self.g, self.t) / 2
        best = self.history[0][1]
        for t, s in self.history:
            if t > back:
                break
            best = s
        return best

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        if isinstance(control, int):
            self.send(control, dt)
        t0 = self.t
        self.t += dt
        on = active(self.queue, t0, self.t)
        self.queue = [q for q in self.queue if q[0] + q[2] > self.t]
        self.state = advance(self.g, self.state, on, dt)
        self.history.append((self.t, self.state))
        if len(self.history) > 4000:
            self.history = self.history[-3000:]
        s = self.state
        for rx, rz, rr in self.g.rocks:
            if math.hypot(s.x - rx, s.z - rz) < rr + BODY:
                self.result = (False, _('Hit a rock'))
                self._note(0.5, 90.0, 2, 0.5)
                return
        if self.level.tip and abs(s.v) > 0.05 and \
                slope(self.g, s.x, s.z, s.heading) > self.level.tip:
            self.result = (False, _('Tipped over on a slope'))
            self._note(0.5, 90.0, 2, 0.5)
            return
        fx, fz = self.g.flags[self.reached]
        if math.hypot(s.x - fx, s.z - fz) < FLAG:
            self.reached += 1
            self._note(0.25, 880.0, 1, 0.3)
            if self.reached == len(self.g.flags):
                self.result = (True, _('Every flag in %.0f s') % self.t)
                return
        if self.t > self.g.seconds:
            self.result = (False, _('%d of %d flags') % (
                self.reached, len(self.g.flags)))


def act(run: Run, port: int) -> None:
    pass


def _ahead(run: Run) -> State:
    """Where the rover will be when a command sent now arrives: the
    true state carried on under the commands already on their way."""
    g = run.g
    s = run.state
    arrive = run.t + delay_at(g, run.t) / 2
    t = run.t
    dt = 1 / 30.0
    while t < arrive - 1e-9:
        step = min(dt, arrive - t)
        s = advance(g, s, active(run.queue, t, t + step), step)
        t += step
    return s


CELL = 1.0
HEADINGS = [(dx, dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dz]
_ROUTES: dict = {}


def route(g: Ground) -> List[Tuple[float, float]]:
    """A way through: from the start to each flag in turn, on a grid,
    clear of the rocks and never across a slope too steep to stand."""
    if g in _ROUTES:
        return _ROUTES[g]
    import heapq
    lv = g.level
    pts = [(0.0, 0.0)] + list(g.flags)
    lo_x = min(x for x, _z in pts) - 12
    lo_z = min(z for _x, z in pts) - 12
    hi_x = max(x for x, _z in pts) + 12
    hi_z = max(z for _x, z in pts) + 12
    nx, nz = int((hi_x - lo_x) / CELL) + 1, int((hi_z - lo_z) / CELL) + 1

    def at(i, j):
        return lo_x + i * CELL, lo_z + j * CELL

    blocked = set()
    for rx, rz, rr in g.rocks:
        reach = rr + BODY + 0.9
        for i in range(int((rx - reach - lo_x) / CELL) - 1,
                       int((rx + reach - lo_x) / CELL) + 2):
            for j in range(int((rz - reach - lo_z) / CELL) - 1,
                           int((rz + reach - lo_z) / CELL) + 2):
                x, z = at(i, j)
                if math.hypot(x - rx, z - rz) < reach:
                    blocked.add((i, j))
    steep: dict = {}

    def fine(i, j, d):
        if not lv.tip:
            return True
        key = (i, j, d)
        if key not in steep:
            x, z = at(i, j)
            h = math.atan2(*HEADINGS[d])
            steep[key] = max(slope(g, x, z, h), slope(
                g, x + HEADINGS[d][0] * CELL / 2,
                z + HEADINGS[d][1] * CELL / 2, h)) < lv.tip * 0.7
        return steep[key]

    path: List[Tuple[float, float]] = []
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        si, sj = round((ax - lo_x) / CELL), round((az - lo_z) / CELL)
        ti, tj = round((bx - lo_x) / CELL), round((bz - lo_z) / CELL)
        best = {(si, sj, -1): 0.0}
        came = {}
        heap = [(0.0, 0.0, si, sj, -1)]
        found = None
        while heap:
            _f, cost, i, j, d = heapq.heappop(heap)
            if cost > best.get((i, j, d), 1e18):
                continue
            if abs(i - ti) <= 1 and abs(j - tj) <= 1:
                found = (i, j, d)
                break
            for e, (di, dj) in enumerate(HEADINGS):
                ni, nj = i + di, j + dj
                if not (0 <= ni < nx and 0 <= nj < nz) or \
                        (ni, nj) in blocked or not fine(i, j, e):
                    continue
                c = cost + math.hypot(di, dj) + (0.4 if d not in (-1, e)
                                                 else 0.0)
                if c < best.get((ni, nj, e), 1e18):
                    best[(ni, nj, e)] = c
                    came[(ni, nj, e)] = (i, j, d)
                    heapq.heappush(heap, (c + math.hypot(ti - ni, tj - nj),
                                          c, ni, nj, e))
        if found is None:
            _ROUTES[g] = []
            return []
        leg = []
        node = found
        while node in came:
            leg.append(at(node[0], node[1]))
            node = came[node]
        path.extend(reversed(leg))
        path.append((bx, bz))
    if len(_ROUTES) > 64:
        _ROUTES.clear()
    _ROUTES[g] = path
    return path


def autopilot(run: Run) -> List[int]:
    """Plans from where the rover will be when the command lands, and
    follows a way found clear of rocks and steep cross-slopes: slow
    enough for the delay, steering for a point a little way along it."""
    if run.result is not None:
        return []
    g, lv = run.g, run.level
    path = route(g)
    if not path:
        return []
    s = _ahead(run)
    k = getattr(run, '_along', 0)
    while k + 1 < len(path) and math.hypot(path[k][0] - s.x,
                                           path[k][1] - s.z) < 2.5:
        k += 1
    # never skip past the next flag
    fx, fz = g.flags[run.reached]
    run._along = k
    tx, tz = path[k]
    want = math.atan2(tx - s.x, tz - s.z)
    err = (want - s.heading + math.pi) % (2 * math.pi) - math.pi
    top = 1.6 if lv.delay < 1 else 1.1
    if abs(err) > 0.3:
        top = 0.7
    if abs(err) > 0.04 and s.v > 0.2:
        return [RIGHT if err > 0 else LEFT]
    if s.v < top - 0.05:
        return [DRIVE]
    if s.v > top + 0.15:
        return [BRAKE]
    return []


def play(g: Ground, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(g)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
