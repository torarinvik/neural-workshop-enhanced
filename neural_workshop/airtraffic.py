# -*- coding: utf-8 -*-
"""Air Traffic: bring every plane down, one at a time, without a loss.

Planes enter the airspace from its edges and fly straight until told
otherwise. The controller picks a plane and gives it one of four
instructions: **hold** (circle where it is), **turn left** or **turn
right** (45 degrees each), or **land** (fly the approach to the runway
of its colour and touch down). A plane that reaches a runway still in
use, or one that has closed, goes around and must be cleared again.
Everything else is a loss: two planes closer than the separation
minimum, a plane in a storm cell, a plane out of fuel, a plane out of
the airspace.

The ladder:

* rungs 1-3: one runway, planes arriving well apart;
* rungs 4-6: two runways, each plane bound for one by its colour;
* rungs 7-9: storm cells drifting across;
* rungs 10-12: fuel -- each plane can only stay up so long;
* rungs 13-15: a runway closes for a while mid-round;
* rungs 16-19: the wind turns round, and both runways with it;
* from rung 20: denser, faster traffic every rung.

A trial passes when every plane has landed and nothing was lost.
Clocked: the planes fly.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

WORLD_W, WORLD_H = 160.0, 100.0
#: Closer than this and two planes are lost.
SEPARATION = 3.5
#: Planes this close are drawn with a warning ring.
WARNING = 9.0
#: Degrees a second, for a commanded turn and for a hold.
TURN_RATE = 50.0
HOLD_RATE = 70.0
#: How far out the approach fix sits from the runway threshold.
FIX = 30.0
#: Most planes in the air at once, and so the slots that name them.
SLOTS = 8
HOLD, LEFT, RIGHT, LAND = range(4)
#: Agent ports: select a slot, then the four instructions.
PORTS = SLOTS + 4


class Grade(NamedTuple):
    rung: int
    planes: int
    interval: float
    speed: float
    runways: int
    storms: int
    fuel: Optional[float]
    closure: bool
    wind_shift: bool
    occupy: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        planes=(3 if r < 4 else 5 if r < 10 else 6 if r < 20
                else min(12, 7 + top // 2)),
        interval=(14.0 if r < 4 else 12.0 if r < 10 else 11.0 if r < 20
                  else max(5.0, 9.0 - 0.35 * top)),
        speed=6.0 if r < 10 else (7.0 if r < 20 else min(9.5, 7.5 + 0.2 * top)),
        runways=1 if r < 4 else 2,
        storms=0 if r < 7 else (1 if r < 13 else 2 if r < 20 else 3),
        fuel=None if r < 10 else (125.0 if r < 20 else max(70.0, 105.0 - 3.5 * top)),
        closure=r >= 13,
        wind_shift=r >= 16,
        occupy=3.0)


class Runway(NamedTuple):
    x: float
    y: float
    #: Heading a landing plane flies, degrees.
    heading: float
    length: float


class Arrival(NamedTuple):
    due: float
    x: float
    y: float
    heading: float
    runway: int
    fuel: Optional[float]


class StormPlan(NamedTuple):
    x: float
    y: float
    vx: float
    vy: float
    radius: float


class Sky(NamedTuple):
    rung: int
    level: Grade
    runways: Tuple[Runway, ...]
    arrivals: Tuple[Arrival, ...]
    storms: Tuple[StormPlan, ...]
    #: (runway, from, until) when a runway is shut, or None.
    closure: Optional[Tuple[int, float, float]]
    #: When the wind turns round, or None.
    shift: Optional[float]
    seconds: float


def _entry(draw: random.Random) -> Tuple[float, float, float]:
    """A point just inside an edge and a heading in towards the field."""
    side = draw.randrange(4)
    if side == 0:
        x, y = 2.0, draw.uniform(15, WORLD_H - 15)
    elif side == 1:
        x, y = WORLD_W - 2.0, draw.uniform(15, WORLD_H - 15)
    elif side == 2:
        x, y = draw.uniform(20, WORLD_W - 20), 2.0
    else:
        x, y = draw.uniform(20, WORLD_W - 20), WORLD_H - 2.0
    aim = math.degrees(math.atan2(WORLD_H / 2 - y, WORLD_W / 2 - x))
    return x, y, aim + draw.uniform(-25, 25)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Sky:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    heading = draw.choice((0.0, 180.0, 30.0, 210.0, -30.0, 150.0))
    if level.runways == 1:
        runways = (Runway(WORLD_W / 2, WORLD_H / 2, heading, 16.0),)
    else:
        rad = math.radians(heading + 90)
        off = 9.0
        runways = tuple(Runway(WORLD_W / 2 + math.cos(rad) * off * side,
                               WORLD_H / 2 + math.sin(rad) * off * side,
                               heading, 16.0) for side in (-1, 1))
    arrivals: List[Arrival] = []
    t = draw.uniform(1.0, 3.0)
    last_side = None
    for k in range(level.planes):
        for _try in range(20):
            x, y, h = _entry(draw)
            side = (round(x), round(y))
            if last_side is None or math.hypot(x - last_side[0],
                                               y - last_side[1]) > 40:
                break
        last_side = (x, y)
        arrivals.append(Arrival(round(t, 2), x, y, h,
                                k % level.runways if level.runways > 1
                                else 0, level.fuel))
        t += level.interval * draw.uniform(0.75, 1.25)
    storms = []
    for _k in range(level.storms):
        x = draw.choice((draw.uniform(15, 50), draw.uniform(110, 145)))
        y = draw.uniform(20, WORLD_H - 20)
        ang = draw.uniform(0, 2 * math.pi)
        storms.append(StormPlan(x, y, math.cos(ang) * 0.9,
                                math.sin(ang) * 0.9, draw.uniform(6, 8.5)))
    last = arrivals[-1].due
    seconds = last + 70.0 + 10.0 * level.planes / 2
    closure = None
    if level.closure:
        start = draw.uniform(0.25, 0.5) * last + 5
        closure = (draw.randrange(level.runways), start, start + 20.0)
    shift = draw.uniform(0.4, 0.7) * last + 8 if level.wind_shift else None
    return Sky(level.rung, level, runways, tuple(arrivals), tuple(storms),
               closure, shift, round(seconds, 1))


def _wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


class Plane:
    def __init__(self, number: int, arrival: Arrival, slot: int) -> None:
        self.number = number
        self.arrival = arrival
        self.slot = slot
        self.x, self.y = arrival.x, arrival.y
        self.heading = arrival.heading
        self.target = arrival.heading
        self.mode = 'free'          # free, hold, approach, final, landed
        self.fuel = arrival.fuel
        self.cleared = False

    @property
    def runway(self) -> int:
        return self.arrival.runway


class Storm:
    def __init__(self, plan: StormPlan) -> None:
        self.x, self.y = plan.x, plan.y
        self.vx, self.vy = plan.vx, plan.vy
        self.radius = plan.radius


class Run:
    def __init__(self, sky: Sky) -> None:
        self.sky = sky
        self.t = 0.0
        self.waiting = list(enumerate(sky.arrivals))
        self.planes: List[Plane] = []
        self.landed: List[int] = []
        self.storms = [Storm(p) for p in sky.storms]
        self.busy_until = [0.0] * len(sky.runways)
        self.selected: Optional[int] = None
        self.result: Optional[Tuple[bool, str]] = None
        self.lost_at: Optional[Tuple[float, float]] = None
        self.notes: List[Tuple[float, str, float, float]] = []
        self.flipped = False

    # --- the runways ------------------------------------------------------

    def runway_heading(self, k: int) -> float:
        h = self.sky.runways[k].heading
        return h + 180.0 if self.flipped else h

    def threshold(self, k: int) -> Tuple[float, float]:
        rw = self.sky.runways[k]
        h = math.radians(self.runway_heading(k))
        return (rw.x - math.cos(h) * rw.length / 2,
                rw.y - math.sin(h) * rw.length / 2)

    def fix(self, k: int) -> Tuple[float, float]:
        tx, ty = self.threshold(k)
        h = math.radians(self.runway_heading(k))
        return tx - math.cos(h) * FIX, ty - math.sin(h) * FIX

    def closed(self, k: int) -> bool:
        c = self.sky.closure
        return c is not None and c[0] == k and c[1] <= self.t < c[2]

    # --- instructions -----------------------------------------------------

    def plane_in(self, slot: int) -> Optional[Plane]:
        for p in self.planes:
            if p.slot == slot:
                return p
        return None

    def select(self, slot: int) -> None:
        if self.plane_in(slot) is not None:
            self.selected = slot

    def order(self, what: int) -> None:
        if self.result is not None or self.selected is None:
            return
        p = self.plane_in(self.selected)
        if p is None:
            return
        if what == HOLD:
            p.mode, p.cleared = 'hold', False
        elif what in (LEFT, RIGHT):
            base = p.target if p.mode == 'free' else p.heading
            p.target = base + (45.0 if what == LEFT else -45.0)
            p.mode, p.cleared = 'free', False
        elif what == LAND:
            p.mode, p.cleared = 'approach', True

    # --- the clock --------------------------------------------------------

    def step(self, dt: float) -> None:
        if self.result is not None:
            return
        self.t += dt
        sky = self.sky
        if sky.shift is not None and not self.flipped and self.t >= sky.shift:
            self.flipped = True
            for p in self.planes:
                if p.mode in ('approach', 'final'):
                    self._go_around(p, _('wind change'))
        while self.waiting and self.waiting[0][1].due <= self.t:
            used = {p.slot for p in self.planes}
            free = [s for s in range(SLOTS) if s not in used]
            if not free:
                break
            number, arrival = self.waiting.pop(0)
            self.planes.append(Plane(number, arrival, free[0]))
        for s in self.storms:
            s.x += s.vx * dt
            s.y += s.vy * dt
            if not s.radius < s.x < WORLD_W - s.radius:
                s.vx = -s.vx
            if not s.radius < s.y < WORLD_H - s.radius:
                s.vy = -s.vy
        speed = sky.level.speed
        for p in list(self.planes):
            self._fly(p, dt, speed)
            if self.result is not None:
                return
        self._separation()
        if self.result is None and not self.planes and not self.waiting:
            self.result = (True, _('All %d planes down safely')
                           % len(sky.arrivals))
        elif self.result is None and self.t >= sky.seconds:
            self.result = (False, _('Time: %d of %d planes down')
                           % (len(self.landed), len(sky.arrivals)))

    def _turn_towards(self, p: Plane, want: float, dt: float) -> None:
        diff = _wrap(want - p.heading)
        most = TURN_RATE * dt
        p.heading += max(-most, min(most, diff))

    def _fly(self, p: Plane, dt: float, speed: float) -> None:
        if p.mode == 'hold':
            p.heading += HOLD_RATE * dt
        elif p.mode == 'free':
            self._turn_towards(p, p.target, dt)
        elif p.mode == 'approach':
            fx, fy = self.fix(p.runway)
            self._turn_towards(p, math.degrees(math.atan2(fy - p.y,
                                                          fx - p.x)), dt)
            if math.hypot(fx - p.x, fy - p.y) < 4.0:
                p.mode = 'final'
        elif p.mode == 'final':
            # Centreline guidance: aim at a point on the extended
            # centreline a little beyond the plane's foot on it.
            tx, ty = self.threshold(p.runway)
            h = math.radians(self.runway_heading(p.runway))
            ux, uy = math.cos(h), math.sin(h)
            along = (p.x - tx) * ux + (p.y - ty) * uy
            aim = min(along + 11.0, 0.5)
            self._turn_towards(p, math.degrees(math.atan2(
                ty + uy * aim - p.y, tx + ux * aim - p.x)), dt)
            if math.hypot(tx - p.x, ty - p.y) < 2.5:
                self._touch_down(p)
                return
            if along > 4.0:
                self._go_around(p, _('missed the runway'))
        h = math.radians(p.heading)
        p.x += math.cos(h) * speed * dt
        p.y += math.sin(h) * speed * dt
        if p.fuel is not None:
            p.fuel -= dt
            if p.fuel <= 0:
                self._lose(p, _('Plane %d ran out of fuel') % (p.slot + 1))
                return
        if not (-1.0 <= p.x <= WORLD_W + 1 and -1.0 <= p.y <= WORLD_H + 1):
            self._lose(p, _('Plane %d left the airspace') % (p.slot + 1))
            return
        for s in self.storms:
            if math.hypot(p.x - s.x, p.y - s.y) < s.radius:
                self._lose(p, _('Plane %d flew into a storm')
                           % (p.slot + 1))
                return

    def _touch_down(self, p: Plane) -> None:
        k = p.runway
        aligned = abs(_wrap(p.heading - self.runway_heading(k))) < 35
        if self.closed(k):
            self._go_around(p, _('runway closed'))
        elif self.t < self.busy_until[k]:
            self._go_around(p, _('runway busy'))
        elif not aligned:
            self._go_around(p, _('not lined up'))
        else:
            self.busy_until[k] = self.t + self.sky.level.occupy
            self.planes.remove(p)
            self.landed.append(p.number)
            self.notes.append((self.t, _('landed'), p.x, p.y))
            if self.selected == p.slot:
                self.selected = None

    def _go_around(self, p: Plane, why: str) -> None:
        p.mode, p.cleared = 'free', False
        p.target = p.heading
        self.notes.append((self.t, _('go around: %s') % why, p.x, p.y))

    def _lose(self, p: Plane, words: str) -> None:
        self.lost_at = (p.x, p.y)
        self.result = (False, words)

    def _separation(self) -> None:
        ps = self.planes
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                if math.hypot(a.x - b.x, a.y - b.y) < SEPARATION:
                    self.lost_at = ((a.x + b.x) / 2, (a.y + b.y) / 2)
                    self.result = (False, _('Planes %d and %d collided')
                                   % (a.slot + 1, b.slot + 1))
                    return

    def close_pairs(self) -> List[Tuple[Plane, Plane]]:
        ps = self.planes
        return [(a, b) for i, a in enumerate(ps) for b in ps[i + 1:]
                if math.hypot(a.x - b.x, a.y - b.y) < WARNING]


# --- a reference controller ----------------------------------------------

def _storm_at(s: Storm, later: float) -> Tuple[float, float]:
    """Where a storm will be *later* seconds on, bounces included."""
    def fold(v: float, lo: float, hi: float) -> float:
        span = hi - lo
        v = (v - lo) % (2 * span)
        return lo + (v if v <= span else 2 * span - v)
    return (fold(s.x + s.vx * later, s.radius, WORLD_W - s.radius),
            fold(s.y + s.vy * later, s.radius, WORLD_H - s.radius))


def _threatened(run: Run, x: float, y: float, margin: float,
                horizon: float = 8.0) -> Optional[Storm]:
    for s in run.storms:
        for k in range(5):
            sx, sy = _storm_at(s, horizon * k / 4)
            if math.hypot(x - sx, y - sy) < s.radius + margin:
                return s
    return None


def _future(run: Run, p: Plane, seconds: float = 6.0, step: float = 0.5
            ) -> List[Tuple[float, float]]:
    """Where *p* will be over the next few seconds if left alone."""
    x, y, h = p.x, p.y, p.heading
    speed = run.sky.level.speed
    out = []
    t = 0.0
    while t < seconds:
        if p.mode == 'hold':
            h += HOLD_RATE * step
        elif p.mode == 'free':
            diff = _wrap(p.target - h)
            h += max(-TURN_RATE * step, min(TURN_RATE * step, diff))
        else:
            gx, gy = run.fix(p.runway) if p.mode == 'approach' else \
                run.threshold(p.runway)
            diff = _wrap(math.degrees(math.atan2(gy - y, gx - x)) - h)
            h += max(-TURN_RATE * step, min(TURN_RATE * step, diff))
        x += math.cos(math.radians(h)) * speed * step
        y += math.sin(math.radians(h)) * speed * step
        out.append((x, y))
        t += step
    return out


def _conflict(run: Run) -> Optional[Tuple[Plane, Plane]]:
    tracks = {p.number: _future(run, p) for p in run.planes}
    worst = None
    for i, a in enumerate(run.planes):
        for b in run.planes[i + 1:]:
            close = min(math.hypot(ax - bx, ay - by) for (ax, ay), (bx, by)
                        in zip(tracks[a.number], tracks[b.number]))
            close = min(close, math.hypot(a.x - b.x, a.y - b.y))
            if close < SEPARATION + 3.0 and (worst is None or
                                             close < worst[0]):
                worst = (close, a, b)
    return None if worst is None else (worst[1], worst[2])


def autopilot(run: Run) -> List[int]:
    """Ports a steady controller sends now.

    Planes hold once well inside the airspace, away from storms and
    from each other; a plane a storm is drifting towards is turned away
    from it (and back towards the middle). One plane at a time per
    runway is cleared to land -- least fuel first, else longest
    waiting -- when the runway is open, the wind will not turn before
    it is down, and its whole approach stays clear of the other planes
    and of where the storms will be when it passes.
    """
    sky = run.sky
    speed = sky.level.speed
    radius = speed / math.radians(HOLD_RATE)
    ports: List[int] = []

    def tell(p: Plane, what: int) -> List[int]:
        if run.selected != p.slot:
            ports.append(p.slot)
        ports.append(SLOTS + what)
        return ports

    def steer(p: Plane, want: float) -> Optional[List[int]]:
        base = p.target if p.mode == 'free' else p.heading
        diff = _wrap(want - base)
        if p.mode != 'free' or abs(diff) > 25:
            return tell(p, LEFT if diff > 0 else RIGHT)
        return None

    def away_from(p: Plane, s: Storm) -> float:
        ax, ay = p.x - s.x, p.y - s.y
        n = math.hypot(ax, ay) or 1.0
        cx, cy = WORLD_W / 2 - p.x, WORLD_H / 2 - p.y
        m = math.hypot(cx, cy) or 1.0
        return math.degrees(math.atan2(ay / n + 0.7 * cy / m,
                                       ax / n + 0.7 * cx / m))

    clash = _conflict(run)
    if clash is not None:
        a, b = clash
        # Act on the one not landing; between two free planes, the
        # later; a holding plane gives way by turning out of its circle.
        order = sorted((a, b), key=lambda p: (p.cleared, p.mode == 'hold',
                                              -p.number))
        mover, other = order[0], order[1]
        room = radius * 2 + 1.5
        fits = (room < mover.x < WORLD_W - room and
                room < mover.y < WORLD_H - room)
        if mover.mode == 'free' and not mover.cleared:
            away = math.degrees(math.atan2(mover.y - other.y,
                                           mover.x - other.x))
            if abs(_wrap(mover.heading - away)) > 90:
                if fits:
                    return tell(mover, HOLD)
                centre = math.degrees(math.atan2(WORLD_H / 2 - mover.y,
                                                 WORLD_W / 2 - mover.x))
                done = steer(mover, (away + centre) / 2 if abs(
                    _wrap(away - centre)) < 150 else centre)
                if done:
                    return done
        elif mover.mode == 'hold':
            away = math.degrees(math.atan2(mover.y - other.y,
                                           mover.x - other.x))
            done = steer(mover, away)
            if done:
                return done
        elif mover.cleared and other.cleared is False:
            pass
    margin = radius * 2 + 5
    for p in run.planes:
        storm = _threatened(run, p.x, p.y, margin)
        if storm is not None and (not p.cleared or not _path_clear(run, p)):
            done = steer(p, away_from(p, storm))
            if done:
                return done
            continue
        if p.cleared:
            continue
        if p.mode == 'free':
            inside = (radius * 2.6 < p.x < WORLD_W - radius * 2.6 and
                      radius * 2.6 < p.y < WORLD_H - radius * 2.6)
            crowd = any(math.hypot(p.x - o.x, p.y - o.y) < radius * 2.4 + 3
                        for o in run.planes if o is not p)
            if inside and not crowd:
                return tell(p, HOLD)
            if not inside:
                centre = math.degrees(math.atan2(WORLD_H / 2 - p.y,
                                                 WORLD_W / 2 - p.x))
                if abs(_wrap(p.target - centre)) > 70:
                    done = steer(p, centre)
                    if done:
                        return done
    for k in range(len(sky.runways)):
        if any(p.cleared and p.runway == k for p in run.planes):
            continue
        if run.closed(k):
            continue
        c = sky.closure
        if c is not None and c[0] == k and run.t < c[1] and run.t + 25 > c[1]:
            continue
        if sky.shift is not None and not run.flipped and \
                run.t + 25 > sky.shift:
            continue
        waiting = [p for p in run.planes if p.runway == k and
                   p.mode in ('hold', 'free') and not p.cleared]
        waiting.sort(key=lambda p: (p.fuel if p.fuel is not None else 0,
                                    p.number))
        for p in waiting:
            if _path_clear(run, p):
                return tell(p, LAND)
    return ports


def _path_clear(run: Run, p: Plane) -> bool:
    """No other plane near the line from *p* to the fix and on to the
    threshold, and no storm where it will be when *p* gets there."""
    fix = run.fix(p.runway)
    tx, ty = run.threshold(p.runway)
    legs = ((p.x, p.y, fix[0], fix[1]), (fix[0], fix[1], tx, ty))
    speed = run.sky.level.speed
    radius = speed / math.radians(HOLD_RATE)
    for ax, ay, bx, by in legs:
        for o in run.planes:
            if o is p:
                continue
            reach = radius * 2 + SEPARATION + 2 if o.mode == 'hold' else \
                SEPARATION + 6
            if _near_segment(o.x, o.y, ax, ay, bx, by) < reach:
                return False
    gone = 0.0
    for ax, ay, bx, by in legs:
        length = math.hypot(bx - ax, by - ay)
        for k in range(int(length // 4) + 1):
            f = min(1.0, k * 4 / max(length, 1e-6))
            x, y = ax + (bx - ax) * f, ay + (by - ay) * f
            when = (gone + f * length) / speed + 2.0
            for s in run.storms:
                sx, sy = _storm_at(s, when)
                if math.hypot(x - sx, y - sy) < s.radius + 5:
                    return False
        gone += length
    return True


def _near_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    f = 0.0 if span == 0 else max(0.0, min(1.0, ((px - ax) * dx +
                                                 (py - ay) * dy) / span))
    return math.hypot(px - (ax + f * dx), py - (ay + f * dy))


def apply(run: Run, port: int) -> None:
    if port < SLOTS:
        run.select(port)
    elif port < PORTS:
        run.order(port - SLOTS)


def play(sky: Sky, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(sky)
    while run.result is None:
        for port in pilot(run):
            apply(run, port)
        run.step(dt)
    return run.result
