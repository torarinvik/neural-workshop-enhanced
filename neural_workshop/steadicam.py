# -*- coding: utf-8 -*-
"""Steadicam: keep the walker in the frame.

A camera on a tripod in a park, and someone walking a winding path
among the trees. Pan, tilt and zoom to keep them inside the framing box
drawn on the viewfinder. The round passes when they were framed for
enough of the time, and fails at once if they are lost for three
seconds.

* rung 1: a slow walker, far off, a big box;
* rungs 2-3: winding paths that pass near the camera, faster;
* rungs 4-6: the walker must also fill a share of the frame's height:
  zoom in when they are far, out when they come near;
* rungs 7-9: the head has weight -- a pan keeps going and has to be
  caught -- and walkers stop and break into a run;
* rungs 10-12: lead room: the walker sits in the third of the frame
  behind them, the space ahead left open;
* rungs 13 and up: several people; the one to follow changes on a cue,
  more and more often; the box shrinks, the pace rises to a jog, and
  the share of the time they must be framed keeps growing.

For the agent boundary: ports 0-5 pan left and right, tilt up and down,
zoom in and out, for the step they are sent in.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

PAN_L, PAN_R, TILT_U, TILT_D, ZOOM_IN, ZOOM_OUT = range(6)
PORTS = 6
EVENTS = ()
EYE = 1.5
ASPECT = 0.62                  # frame height over width
PAN = math.radians(55)         # a second, at full speed
ZOOM = 0.9                     # field of view, by this a second (log)
FOV = (math.radians(14), math.radians(70))
LOST = 3.0
PERSON = 1.75
COLOURS = (_('red'), _('blue'), _('yellow'), _('green'))
PATCHES = ('wood', 'bell')


class Grade(NamedTuple):
    rung: int
    speed: float               # metres a second
    wind: float                # how much the path winds
    near: float                # the closest it comes
    box: float                 # half-width of the box, share of the frame
    size: Tuple[float, float]  # share of the frame's height, or (0, 0)
    heavy: bool                # pan and tilt carry on
    moods: bool                # stops and runs
    lead: bool
    people: int
    cue: float                 # seconds between switches
    seconds: float
    need: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    size = (0.0, 0.0)
    if r >= 4:
        size = (0.22, 0.65) if r < 10 else (0.28, 0.6)
    if r == 1:
        return Grade(r, 1.0, 0.2, 14.0, 0.6, size, False, False, False, 1,
                     0.0, 25.0, 0.8)
    if r < 4:
        return Grade(r, 1.4 + 0.3 * (r - 2), 0.6, 6.0, 0.5, size, False,
                     False, False, 1, 0.0, 30.0, 0.82)
    if r < 7:
        return Grade(r, 1.6, 0.7, 6.0, 0.5, size, False, False, False, 1,
                     0.0, 30.0, 0.82)
    if r < 10:
        return Grade(r, 1.8, 0.8, 5.0, 0.45, size, True, True, False, 1,
                     0.0, 35.0, 0.82)
    if r < 13:
        return Grade(r, 1.8, 0.8, 5.0, 0.42, size, True, True, True, 1,
                     0.0, 35.0, 0.8)
    return Grade(r, min(4.5, 2.0 + 0.1 * (r - 13)), 0.9, 5.0,
                 max(0.2, 0.4 * 0.95 ** (r - 13)), size, True, True, True,
                 min(4, 2 + (r - 13) // 4), max(3.0, 9.0 - 0.4 * (r - 13)),
                 40.0, min(0.85, 0.78 + 0.002 * (r - 13)))


class Walker(NamedTuple):
    points: Tuple[Tuple[float, float], ...]   # (x, z) along the path
    pace: Tuple[float, ...]                   # speed factor at each


class Park(NamedTuple):
    level: Grade
    walkers: Tuple[Walker, ...]
    trees: Tuple[Tuple[float, float, float], ...]   # x, z, radius
    cues: Tuple[Tuple[float, int], ...]             # from when, whom
    start: Tuple[float, float, float]               # yaw, pitch, fov


def _path(level: Grade, draw: random.Random) -> Walker:
    """A walk at a steady pace, sampled every 0.05 s."""
    a = draw.uniform(-0.9, 0.9)
    d = draw.uniform(level.near + 6, level.near + 14)
    x, z = d * math.sin(a), d * math.cos(a)
    heading = draw.uniform(0, 2 * math.pi)
    pts, pace = [], []
    turn = 0.0
    p = 1.0
    t = 0.0
    while t < level.seconds + 2:
        if draw.random() < 0.02:
            turn = draw.uniform(-1, 1) * level.wind
        if level.moods and draw.random() < 0.006:
            p = draw.choice((0.0, 0.0, 1.0, 1.8))
        elif draw.random() < 0.004:
            p = 1.0
        heading += turn * 0.05
        # keep within the park and out of the camera's lap
        r = math.hypot(x, z)
        if r > 32 or z < 2.0 or r < level.near:
            want = math.atan2(-x, 18 - z) if r > 32 or z < 2.0 else \
                math.atan2(x, z)
            diff = (want - heading + math.pi) % (2 * math.pi) - math.pi
            heading += max(-0.15, min(0.15, diff))
        x += math.sin(heading) * level.speed * p * 0.05
        z += math.cos(heading) * level.speed * p * 0.05
        pts.append((x, z))
        pace.append(p)
        t += 0.05
    return Walker(tuple(pts), tuple(pace))


def where(w: Walker, t: float) -> Tuple[float, float]:
    i = max(0.0, t / 0.05)
    k = min(len(w.points) - 2, int(i))
    f = min(1.0, i - k)
    (ax, az), (bx, bz) = w.points[k], w.points[k + 1]
    return ax + (bx - ax) * f, az + (bz - az) * f


def angles(x: float, z: float, y: float = PERSON / 2
           ) -> Tuple[float, float, float]:
    """Pan and tilt that point at (x, y, z), and how far it is."""
    h = math.hypot(x, z)
    return math.atan2(x, z), math.atan2(y - EYE, h), math.hypot(h, y - EYE)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Park:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(60):
        walkers = tuple(_path(level, draw) for _p in range(level.people))
        trees = tuple((draw.uniform(-25, 25), draw.uniform(4, 35),
                       draw.uniform(0.3, 0.7)) for _t in range(30))
        cues = [(0.0, 0)]
        if level.people > 1:
            t = level.cue
            while t < level.seconds:
                # the next to follow: whoever is nearest the one followed
                # now, as seen from the camera
                now = cues[-1][1]
                a0 = math.atan2(*where(walkers[now], t))
                nxt = min((k for k in range(level.people) if k != now),
                          key=lambda k: abs(math.atan2(*where(walkers[k], t))
                                            - a0))
                cues.append((t, nxt))
                t += level.cue * draw.uniform(0.8, 1.2)
        x, z = where(walkers[cues[0][1]], 0.0)
        yaw, pitch, _r = angles(x, z)
        park = Park(level, walkers, trees, tuple(cues),
                    (yaw, pitch, math.radians(50)))
        if play(park)[0] and not any(
                play(park, lambda run, k=k: [k] if k is not None else [])[0]
                for k in (None,) + tuple(range(PORTS))):
            return park
    raise RuntimeError('steadicam: no park for rung %d' % rung)


class Run(object):
    def __init__(self, park: Park) -> None:
        self.park = park
        self.level = park.level
        self.t = 0.0
        self.yaw, self.pitch, self.fov = park.start
        self.vyaw = self.vpitch = 0.0
        self.framed = 0.0
        self.counted = 0.0
        self.lost_since: Optional[float] = None
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = self.level.seconds
        self.cue_heard = 0

    def whom(self) -> int:
        k = 0
        for t, w in self.park.cues:
            if self.t >= t:
                k = w
        return k

    def subject(self, k: Optional[int] = None) -> Tuple[float, float]:
        return where(self.park.walkers[self.whom() if k is None else k],
                     self.t)

    def motion(self) -> float:
        """Which way the subject moves across the frame over the last
        second: -1 left, 1 right, 0 hardly at all (under 2 degrees a
        second)."""
        w = self.park.walkers[self.whom()]
        x0, z0 = where(w, max(0.0, self.t - 1.0))
        x1, z1 = where(w, self.t)
        d = math.atan2(x1, z1) - math.atan2(x0, z0)
        return 0.0 if abs(d) < math.radians(2) else (1.0 if d > 0 else -1.0)

    def aim(self) -> Tuple[float, float]:
        """Where in the frame the subject should sit (share of half the
        frame, across and up)."""
        if self.level.lead:
            return -0.4 * self.motion(), 0.0
        return 0.0, 0.0

    def place(self) -> Tuple[float, float, float]:
        """Where the subject is in the frame: across and up as shares of
        half the frame, and its height as a share of the frame's."""
        x, z = self.subject()
        a, e, r = angles(x, z)
        da = (a - self.yaw + math.pi) % (2 * math.pi) - math.pi
        half_w = self.fov / 2
        half_h = math.atan(math.tan(half_w) * ASPECT)
        ux = math.tan(da) / math.tan(half_w)
        uy = math.tan(e - self.pitch) / math.tan(half_h)
        tall = 2 * math.atan(PERSON / 2 / r) / (2 * half_h)
        return ux, uy, tall

    def in_frame(self) -> bool:
        ux, uy, tall = self.place()
        ax, ay = self.aim()
        box = self.level.box
        if abs(ux - ax) > box or abs(uy - ay) > box / ASPECT * 0.7:
            return False
        lo, hi = self.level.size
        return hi == 0 or lo <= tall <= hi

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        on = {control} if isinstance(control, int) else set(control or ())
        px = (PAN_R in on) - (PAN_L in on)
        py = (TILT_U in on) - (TILT_D in on)
        slow = max(0.35, self.fov / FOV[1])  # finer when zoomed in
        if self.level.heavy:
            self.vyaw += (px * 3.0 * PAN * slow - 1.2 * self.vyaw) * dt
            self.vpitch += (py * 3.0 * PAN * slow - 1.2 * self.vpitch) * dt
        else:
            self.vyaw, self.vpitch = px * PAN * slow, py * PAN * slow
        self.yaw += self.vyaw * dt
        self.pitch = max(-0.6, min(0.6, self.pitch + self.vpitch * dt))
        z = (ZOOM_OUT in on) - (ZOOM_IN in on)
        self.fov = max(FOV[0], min(FOV[1], self.fov * math.exp(z * ZOOM * dt)))
        cue = sum(1 for t, _w in self.park.cues if self.t >= t)
        if cue != self.cue_heard:
            self.cue_heard = cue
            if cue > 1:
                self.notes.append(Note(self.t, 0.2, 880.0, 0, 0, 0.3, 0.3,
                                       0.8, 1, cue, -1, 0.0))
        if self.t < 1.0:
            return
        switched = any(0 < self.t - t < 1.5 for t, _w in self.park.cues[1:])
        if not switched:                # a moment to find the new one
            self.counted += dt
        if self.in_frame():
            self.framed += dt
            self.lost_since = None
        elif switched:
            pass
        elif self.lost_since is None:
            self.lost_since = self.t
        elif self.t - self.lost_since > LOST:
            self.result = (False, _('Lost them for %d seconds') % LOST)
            return
        if self.t >= self.level.seconds:
            share = self.framed / max(1e-6, self.counted)
            self.result = (share >= self.level.need,
                           _('Framed %d%% of the time, %d%% needed') % (
                               round(100 * share), round(100 *
                                                         self.level.need)))


def act(run: Run, port: int) -> None:
    pass


def autopilot(run: Run) -> List[int]:
    """Points where the subject will be a moment from now, and zooms to
    the middle of the size allowed."""
    if run.result is not None:
        return []
    w = run.park.walkers[run.whom()]
    lead = 0.25 if run.level.heavy else 0.12
    x, z = where(w, run.t + lead)
    a, e, r = angles(x, z)
    ax, ay = run.aim()
    half_w = run.fov / 2
    half_h = math.atan(math.tan(half_w) * ASPECT)
    want_yaw = a - math.atan(ax * math.tan(half_w))
    want_pitch = e - math.atan(ay * math.tan(half_h))
    dy = (want_yaw - run.yaw + math.pi) % (2 * math.pi) - math.pi
    dp = want_pitch - run.pitch
    if run.level.heavy:
        # damp against how fast the subject moves, not against stillness
        x2, z2 = where(w, run.t + lead + 0.2)
        a2, e2, _r2 = angles(x2, z2)
        rate_a = ((a2 - a + math.pi) % (2 * math.pi) - math.pi) / 0.2
        rate_e = (e2 - e) / 0.2
        dy -= (run.vyaw - rate_a) * 0.6
        dp -= (run.vpitch - rate_e) * 0.6
    box = run.level.box
    # errors as shares of what the frame allows: 1 is the edge of the box
    ex = abs(dy) / half_w / box
    ey = abs(dp) / half_h / (box / ASPECT * 0.7)
    ez = 0.0
    zoom: List[int] = []
    lo, hi = run.level.size
    if hi:
        _ux, _uy, tall = run.place()
        mid = (lo + hi) / 2
        ez = abs(tall - mid) / ((hi - lo) / 2)
        zoom = [ZOOM_IN if tall < mid else ZOOM_OUT]
    worst = max(ex, ey, ez)
    if worst < 0.15:
        return []
    if ez == worst:
        return zoom
    if ex == worst:
        return [PAN_R if dy > 0 else PAN_L]
    return [TILT_U if dp > 0 else TILT_D]


def play(park: Park, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(park)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
