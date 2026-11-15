# -*- coding: utf-8 -*-
"""Drone Hoops: fly a little drone through hoops, in order, against the
clock.

A courtyard at dusk, hoops standing in it on poles. The next hoop rings
-- a bell that rings faster the nearer the drone is, higher when the
hoop is above the drone, from the side of the screen it is on -- and on
the first rungs it also glows gold. Steer with the mouse (hold the
button: the drone flies to the spot under the pointer, the wheel sets
its height) or with the keys (arrows / WASD across the screen, Space /
E up, Shift / Q down). The drone keeps its speed for a moment after you
let go; hoops have rims, and clipping one bounces you back.

Controls are relative to the camera: "forward" is into the screen,
whatever the camera is looking at. That is easy while the camera
follows the drone, and the ladder takes it away.

The ladder:

* rungs 1-3: three big hoops, the next one gold; the camera rides
  behind the drone looking at the next hoop;
* rungs 4-6: smaller hoops set at angles; the camera follows the
  drone's heading instead;
* rungs 7-9: the camera cuts between fixed cameras round the yard every
  few seconds -- forward changes with it;
* rungs 10-12: no gold: every hoop looks the same and only the bell
  says which is next; flying through any other hoop loses the run;
* rungs 13-15: hoops bob and turn on their poles; quicker cuts;
* rungs 16-19: gusts of wind (heard coming before they hit), and birds
  that chirp from where they fly;
* from rung 20: the camera also circles the drone, lightning flashes
  and thunders, and from rung 24 a second bell rings from a wrong
  hoop at its own steady pace; more, smaller hoops every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Sequence, Set, Tuple

from .drshape import Note
from .i18n import _

Vec = Tuple[float, float, float]

# Ports: across the screen (and diagonals), and up and down.
(FORWARD, BACK, LEFT, RIGHT, FORWARD_LEFT, FORWARD_RIGHT, BACK_LEFT,
 BACK_RIGHT, UP, DOWN) = range(10)
PORTS = 10
EVENTS: Tuple[int, ...] = ()
_D = 0.7071
PUSH = {FORWARD: (1, 0, 0), BACK: (-1, 0, 0), LEFT: (0, -1, 0),
        RIGHT: (0, 1, 0), FORWARD_LEFT: (_D, -_D, 0),
        FORWARD_RIGHT: (_D, _D, 0), BACK_LEFT: (-_D, -_D, 0),
        BACK_RIGHT: (-_D, _D, 0), UP: (0, 0, 1), DOWN: (0, 0, -1)}

HALF = 18.0                    # the yard runs -HALF..HALF in x and z
CEILING = 11.0
FLOOR = 0.35
ACC = 15.0                     # thrust, units a second squared
CLIMB = 11.0
DRONE = 0.35                   # the drone's radius
RIM = 0.22                     # a hoop's tube
WARN = 1.3                     # a gust is heard this long before it hits
START: Vec = (0.0, 2.5, -HALF + 3.0)
# Voices, by index into PATCHES.
BELL, PASS, KNOCK, HUM, WIND, BIRD, THUNDER = range(7)
PATCHES = ('bell', 'pluck', 'wood', 'sub', 'hiss', 'chirp', 'growl')


class Grade(NamedTuple):
    rung: int
    hoops: int
    radius: float
    drag: float                # how soon the drone stops by itself
    lit: bool                  # the next hoop glows
    camera: str                # 'look', 'follow', 'cuts', 'circle'
    cut: float                 # seconds between cuts
    angle: float               # degrees hoops are turned off the line
    bob: float                 # how far hoops move
    spin: float                # degrees a second hoops turn
    wind: float                # gust strength, 0 for none
    birds: int
    lightning: bool
    decoy: bool                # a second bell on a wrong hoop
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        hoops=(3 if r < 4 else 4 if r < 7 else 5 if r < 13 else 6 if r < 20
               else min(9, 6 + top // 3)),
        radius=(2.6 if r < 4 else 2.1 if r < 7 else 1.9 if r < 13
                else 1.7 if r < 20 else max(1.15, 1.6 - 0.03 * top)),
        drag=(3.0 if r < 4 else 2.2 if r < 10 else 1.7 if r < 20
              else max(1.1, 1.6 - 0.03 * top)),
        lit=r < 10,
        camera=('look' if r < 4 else 'follow' if r < 7 else 'cuts'
                if r < 20 else 'circle'),
        cut=(6.0 if r < 13 else 4.5 if r < 20 else max(2.5, 4.0 - 0.1 * top)),
        angle=15.0 if r < 4 else 35.0 if r < 13 else 55.0,
        bob=0.0 if r < 13 else 1.0 if r < 20 else min(2.2, 1.4 + 0.05 * top),
        spin=0.0 if r < 13 else 14.0 if r < 20 else min(30.0, 16.0 + top),
        wind=0.0 if r < 16 else 9.0 if r < 20 else min(13.0, 9.5 + 0.2 * top),
        birds=0 if r < 16 else 3 if r < 20 else min(8, 4 + top // 3),
        lightning=r >= 20,
        decoy=r >= 24,
        seconds=(15.0 if r < 4 else 13.0 if r < 10 else 12.0 if r < 20
                 else max(8.5, 11.5 - 0.15 * top)))


class Hoop(NamedTuple):
    centre: Vec
    yaw: float                 # radians; the hoop faces along its yaw
    radius: float
    bob: Tuple[float, float, float, float]   # amplitude, rate, phase, axis
    spin: float                # radians a second


class Gust(NamedTuple):
    t: float                   # when it hits
    dur: float
    heading: float             # radians, the way it blows
    strength: float


class Bird(NamedTuple):
    t: float                   # when it sets off
    dur: float
    a: Vec
    b: Vec


class Cut(NamedTuple):
    t: float
    camera: int                # which fixed camera; -1 circles the drone


class Course(NamedTuple):
    level: Grade
    hoops: List[Hoop]
    gusts: List[Gust]
    birds: List[Bird]
    flashes: List[float]
    cuts: List[Cut]
    decoy: int                 # the hoop the second bell rings on, or -1
    circle: Tuple[float, float]   # circling: start angle, turn rate
    seed: int


# --- vectors ----------------------------------------------------------------

def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec) -> Vec:
    n = norm(a) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


# --- the yard's fixed cameras ------------------------------------------------

def fixed_cameras() -> List[Vec]:
    far, high = HALF * 1.25, 9.5
    return [(-far, high, -far), (far, high, -far), (far, high, far),
            (-far, high, far), (0.0, high + 2.0, -far * 1.1),
            (far * 1.1, high + 2.0, 0.0), (0.0, high + 2.0, far * 1.1),
            (-far * 1.1, high + 2.0, 0.0)]


# --- dealing ----------------------------------------------------------------

def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Course:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        course = _build(level, draw)
        if course is None:
            continue
        best = best or course
        if play(course)[0]:
            return course
    return best


def _build(level: Grade, draw: random.Random) -> Optional[Course]:
    hoops: List[Hoop] = []
    at = (START[0], START[2])
    heading = 0.0                       # +z, away from the start wall
    margin = 4.5
    for _k in range(level.hoops):
        for tries in range(80):
            # Gentle turns first; sharper ones only when the yard ends.
            limit = (25.0 if level.rung < 4 or not hoops else 60.0) + \
                2.0 * tries
            turn = math.radians(draw.uniform(-limit, limit))
            h = heading + turn
            dist = draw.uniform(8.5, 12.5)
            x, z = at[0] + math.sin(h) * dist, at[1] + math.cos(h) * dist
            if not (-HALF + margin < x < HALF - margin and
                    -HALF + margin < z < HALF - margin):
                continue
            if any(math.hypot(x - o.centre[0], z - o.centre[2]) < 7.5
                   for o in hoops):
                continue
            break
        else:
            return None
        y = (draw.uniform(2.6, 4.2) if level.rung < 4 else
             draw.uniform(level.radius + 0.6, CEILING - level.radius - 1.4))
        yaw = h + math.radians(draw.uniform(-level.angle, level.angle))
        axis = draw.choice((0.0, 1.0))  # 0 bobs up and down, 1 sideways
        bob = (level.bob * draw.uniform(0.7, 1.0), draw.uniform(0.5, 0.9),
               draw.uniform(0, 2 * math.pi), axis)
        spin = math.radians(level.spin) * draw.choice((-1, 1)) * \
            draw.uniform(0.7, 1.0)
        hoops.append(Hoop((x, y, z), yaw, level.radius, bob, spin))
        at, heading = (x, z), h
    total = level.seconds * level.hoops
    gusts: List[Gust] = []
    if level.wind:
        t = draw.uniform(4.0, 8.0)
        while t < total:
            gusts.append(Gust(round(t, 2), draw.uniform(1.4, 2.4),
                              draw.uniform(0, 2 * math.pi),
                              level.wind * draw.uniform(0.8, 1.0)))
            t += draw.uniform(5.0, 9.0)
    birds: List[Bird] = []
    for _k in range(level.birds * 4):
        t = draw.uniform(0.5, total)
        side = draw.uniform(0, 2 * math.pi)
        a = (math.sin(side) * HALF * 1.4, draw.uniform(4, 10),
             math.cos(side) * HALF * 1.4)
        b = (-a[0] + draw.uniform(-8, 8), draw.uniform(4, 10),
             -a[2] + draw.uniform(-8, 8))
        birds.append(Bird(round(t, 2), draw.uniform(6.0, 10.0), a, b))
    birds.sort()
    flashes: List[float] = []
    if level.lightning:
        t = draw.uniform(3.0, 6.0)
        while t < total:
            flashes.append(round(t, 2))
            t += draw.uniform(4.0, 8.0)
    cuts: List[Cut] = []
    if level.camera in ('cuts', 'circle'):
        n = len(fixed_cameras())
        t, last = 0.0, -2
        while t < total:
            pick = draw.randrange(n)
            if level.camera == 'circle' and draw.random() < 0.4:
                pick = -1
            if pick == last:
                pick = (pick + 1) % n if pick >= 0 else 0
            cuts.append(Cut(round(t, 2), pick))
            last = pick
            t += level.cut * draw.uniform(0.75, 1.25)
    decoy = -1
    if level.decoy and level.hoops > 2:
        decoy = draw.randrange(1, level.hoops)
    circle = (draw.uniform(0, 2 * math.pi),
              math.radians(draw.uniform(18, 30)) * draw.choice((-1, 1)))
    return Course(level, hoops, gusts, birds, flashes, cuts, decoy, circle,
                  draw.randrange(1 << 20))


# --- where things are ----------------------------------------------------------

def hoop_at(h: Hoop, t: float) -> Tuple[Vec, Vec]:
    """The hoop's centre and the way it faces at time *t*."""
    amp, rate, phase, axis = h.bob
    c = h.centre
    if amp:
        s = amp * math.sin(rate * t + phase)
        if axis:
            c = (c[0] + math.cos(h.yaw) * s, c[1], c[2] - math.sin(h.yaw) * s)
        else:
            c = (c[0], c[1] + s, c[2])
    yaw = h.yaw + h.spin * t
    return c, (math.sin(yaw), 0.0, math.cos(yaw))


def bird_at(b: Bird, t: float) -> Optional[Vec]:
    u = (t - b.t) / b.dur
    if not 0.0 <= u <= 1.0:
        return None
    p = add(scale(b.a, 1 - u), scale(b.b, u))
    return (p[0], p[1] + 0.6 * math.sin(u * 9.0), p[2])


def gust_at(course: Course, t: float) -> Optional[Gust]:
    for g in course.gusts:
        if g.t <= t < g.t + g.dur:
            return g
    return None


# --- the run --------------------------------------------------------------------

def _on(control) -> Set[int]:
    if control is None:
        return set()
    if isinstance(control, int):
        return {control}
    return set(control)


class Run:
    def __init__(self, course: Course) -> None:
        self.course = course
        self.level = course.level
        self.t = 0.0
        self.p: Vec = START
        self.v: Vec = (0.0, 0.0, 0.0)
        self.thrust: Vec = (0.0, 0.0, 0.0)
        self.next = 0
        self.passed: List[float] = []
        self.bumps = 0
        self.aim: Optional[Tuple[float, float]] = None     # the mouse
        self.aim_y: Optional[float] = None
        self.yaw = 0.0                 # where a following camera looks
        self.heading = 0.0             # where the drone's nose points
        self.end = self.level.seconds * self.level.hoops
        self.notes: List[Note] = []
        self.seed = 1
        self.chime_at = 0.4
        self.decoy_at = 1.1
        self.hum_at = 0.0
        self.hiss_at = 0.0
        self.chirps = [b.t + 0.3 for b in course.birds]
        self.thunder = list(course.flashes)
        self.result: Optional[Tuple[bool, str]] = None
        self.said = ''
        self._camera_now()

    # --- the camera
    def camera(self) -> Tuple[Vec, Vec, int]:
        """(eye, what it looks at, fixed camera number or -1)."""
        return self.eye, self.look, self.cam

    def cut_now(self) -> Optional[Cut]:
        cuts = self.course.cuts
        now = None
        for c in cuts:
            if c.t <= self.t:
                now = c
            else:
                break
        return now

    def _camera_now(self) -> None:
        level, p = self.level, self.p
        cut = self.cut_now()
        mode = level.camera
        if cut is not None and cut.camera >= 0:
            self.eye = fixed_cameras()[cut.camera]
            self.look = (p[0], p[1] * 0.6, p[2])
            self.cam = cut.camera
            return
        if cut is not None and cut.camera < 0:
            a0, w = self.course.circle
            a = a0 + w * self.t
            self.eye = (p[0] + math.sin(a) * 9.0, p[1] + 4.5,
                        p[2] + math.cos(a) * 9.0)
            self.look = p
            self.cam = -1
            return
        if mode == 'look' and self.next < len(self.course.hoops):
            c, _n = hoop_at(self.course.hoops[self.next], self.t)
            want = math.atan2(c[0] - p[0], c[2] - p[2])
        else:
            want = self.heading
        yaw = self.yaw
        diff = (want - yaw + math.pi) % (2 * math.pi) - math.pi
        self.yaw = yaw + diff * min(1.0, 2.2 * self._dt)
        f = (math.sin(self.yaw), 0.0, math.cos(self.yaw))
        self.eye = (p[0] - f[0] * 7.5, p[1] + 3.2, p[2] - f[2] * 7.5)
        self.look = (p[0] + f[0] * 3.0, p[1] + 0.3, p[2] + f[2] * 3.0)
        self.cam = -2

    _dt = 0.0

    def frame(self) -> Tuple[Vec, Vec]:
        """The camera's forward and right along the ground: what the
        controls push along."""
        f = sub(self.look, self.eye)
        f = unit((f[0], 0.0, f[2]))
        return f, (-f[2], 0.0, f[0])

    # --- flying
    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        t0 = self.t
        self.t += dt
        self._dt = dt
        level = self.level
        f, r = self.frame()
        on = _on(control)
        a, b, c = 0.0, 0.0, 0.0
        for port in on:
            push = PUSH.get(port)
            if push:
                a += push[0]
                b += push[1]
                c += push[2]
        if on:
            self.aim = None
            self.aim_y = None
        k = math.hypot(a, b)
        if k > 1.0:
            a, b = a / k, b / k
        acc = add(scale(f, a * ACC), scale(r, b * ACC))
        acc = (acc[0], max(-1.0, min(1.0, c)) * CLIMB, acc[2])
        if not on and self.aim is not None:
            want = (self.aim[0] - self.p[0], 0.0, self.aim[1] - self.p[2])
            pull = sub(scale(want, 3.0), scale((self.v[0], 0.0, self.v[2]),
                                               1.6))
            n = norm(pull)
            if n > ACC:
                pull = scale(pull, ACC / n)
            acc = (pull[0], acc[1], pull[2])
        if not on and self.aim_y is not None:
            acc = (acc[0], max(-CLIMB, min(CLIMB, 4.0 * (self.aim_y - self.p[1])
                                           - 2.0 * self.v[1])), acc[2])
        self.thrust = acc
        gust = gust_at(self.course, self.t)
        if gust is not None:
            acc = add(acc, (math.sin(gust.heading) * gust.strength, 0.0,
                            math.cos(gust.heading) * gust.strength))
        v = add(self.v, scale(acc, dt))
        v = scale(v, math.exp(-level.drag * dt))
        old = self.p
        p = add(old, scale(v, dt))
        lo = -HALF + DRONE
        hi = HALF - DRONE
        x, y, z = p
        vx, vy, vz = v
        if not lo <= x <= hi:
            x, vx = max(lo, min(hi, x)), -0.3 * vx
            self._knock(0.4)
        if not lo <= z <= hi:
            z, vz = max(lo, min(hi, z)), -0.3 * vz
            self._knock(0.4)
        if not FLOOR <= y <= CEILING:
            y, vy = max(FLOOR, min(CEILING, y)), -0.3 * vy
            if abs(v[1]) > 2.0:
                self._knock(0.3)
        p, v = (x, y, z), (vx, vy, vz)
        if math.hypot(v[0], v[2]) > 0.8:
            self.heading = math.atan2(v[0], v[2])
        self.p, self.v = self._hoops(old, p, v)
        self._camera_now()
        self._sound(t0, self.t)
        if self.result is not None:
            return
        if self.next >= len(self.course.hoops):
            self.result = (True, _('Through every hoop'))
        elif self.t >= self.end:
            self.result = (False, _('Out of time'))

    def _hoops(self, old: Vec, p: Vec, v: Vec) -> Tuple[Vec, Vec]:
        for k, h in enumerate(self.course.hoops):
            c, n = hoop_at(h, self.t)
            a, b = dot(sub(old, c), n), dot(sub(p, c), n)
            if (a > 0) == (b > 0) or a == b:
                continue
            u = a / (a - b)
            cross = add(old, scale(sub(p, old), u))
            d = norm(sub(cross, c))
            if d > h.radius + RIM + DRONE:
                continue
            if d < h.radius - RIM - DRONE * 0.4:
                if k == self.next:
                    self.next += 1
                    self.passed.append(self.t)
                    self._ding(len(self.passed))
                elif k > self.next and not self.level.lit:
                    self.result = (False, _('Through the wrong hoop'))
                continue
            # The rim: bounce back the way it came.
            self.bumps += 1
            self._knock(0.7)
            vn = dot(v, n)
            v = sub(v, scale(n, 1.6 * vn))
            side = 1.0 if a > 0 else -1.0
            p = add(sub(p, scale(n, b)), scale(n, side * 0.05))
        return p, v

    # --- sound
    def _note(self, t: float, dur: float, freq: float, pan: float,
              gain: float, voice: int, bright: float = 0.8) -> None:
        self.seed += 1
        pan = max(-1.0, min(1.0, pan))
        self.notes.append(Note(t, dur, freq, pan, pan, gain, gain, bright,
                               voice, self.seed, -1, 0.0))

    def placed(self, q: Vec) -> Tuple[float, float, bool]:
        """(pan, distance from the drone, in front of the camera) for a
        sound at *q*."""
        eye, look = self.eye, self.look
        f = unit(sub(look, eye))
        r = unit((-f[2], 0.0, f[0]))
        d = sub(q, eye)
        ahead = dot(d, f)
        side = dot(d, r)
        pan = side / max(2.0, abs(ahead))
        return pan, norm(sub(q, self.p)), ahead > 0

    def _bell(self, t: float, k: int, gain: float) -> None:
        c, _n = hoop_at(self.course.hoops[k], t)
        pan, dist, front = self.placed(c)
        rise = max(-1.0, min(1.0, (c[1] - self.p[1]) / 3.0))
        freq = 880.0 * 2 ** (rise * 7 / 12.0)
        self._note(t, 0.35, freq, pan, gain * (0.25 + 0.6 / (1 + dist / 6)),
                   BELL, 0.9 if front else 0.35)

    def _ding(self, n: int) -> None:
        for j, semis in enumerate((0, 4, 7)):
            self._note(self.t + 0.07 * j, 0.25, 523.25 * 2 ** ((semis + n)
                                                              / 12.0),
                       0.0, 0.55, PASS)

    def _knock(self, gain: float) -> None:
        if self.notes and self.notes[-1].voice == KNOCK and \
                self.t - self.notes[-1].t < 0.15:
            return
        self._note(self.t, 0.12, 180.0, 0.0, gain, KNOCK)

    def _sound(self, a: float, b: float) -> None:
        out_from = len(self.notes)
        course, level = self.course, self.level
        if self.next < len(course.hoops) and self.chime_at < b:
            t = max(a, self.chime_at)
            self._bell(t, self.next, 1.0)
            c, _n = hoop_at(course.hoops[self.next], t)
            dist = norm(sub(c, self.p))
            self.chime_at = t + 0.18 + 0.85 * min(1.0, dist / 22.0)
        if course.decoy > self.next and self.decoy_at < b:
            t = max(a, self.decoy_at)
            self._bell(t, course.decoy, 0.8)
            self.decoy_at = t + 0.62
        if self.hum_at < b:
            t = max(a, self.hum_at)
            work = norm(self.thrust) / ACC
            self._note(t, 0.16, 90.0 + 40.0 * work, 0.0,
                       0.05 + 0.07 * work, HUM, 0.4)
            self.hum_at = t + 0.12
        if level.wind and self.hiss_at < b:
            t = max(a, self.hiss_at)
            for g in course.gusts:
                if g.t - WARN <= t < g.t + g.dur:
                    rise = min(1.0, (t - (g.t - WARN)) / WARN)
                    src = (self.p[0] - math.sin(g.heading) * 6, self.p[1],
                           self.p[2] - math.cos(g.heading) * 6)
                    pan, _d, _f = self.placed(src)
                    self._note(t, 0.14, 400.0, pan, 0.08 + 0.3 * rise, WIND,
                               0.5)
                    break
            self.hiss_at = t + 0.1
        for k, bird in enumerate(course.birds):
            if self.chirps[k] < b:
                t = max(a, self.chirps[k])
                q = bird_at(bird, t)
                if q is None:
                    self.chirps[k] = 1e9
                    continue
                pan, dist, front = self.placed(q)
                draw = random.Random(course.seed + 7 * k + int(t * 10))
                for j in range(draw.choice((2, 3))):
                    self._note(t + 0.09 * j, 0.08,
                               draw.uniform(1800, 2600), pan,
                               0.35 / (1 + dist / 10), BIRD)
                self.chirps[k] = t + draw.uniform(0.5, 1.3)
        while self.thunder and self.thunder[0] + 0.6 < b:
            t = max(a, self.thunder.pop(0) + 0.6)
            self._note(t, 1.6, 55.0, 0.0, 0.55, THUNDER, 0.3)
        fresh = self.notes[out_from:]
        if len(fresh) > 1:
            fresh.sort(key=lambda n: n.t)
            self.notes[out_from:] = fresh

    # --- for the screen
    def flash(self) -> float:
        """How bright a lightning flash is now, 0 to 1."""
        for t in self.course.flashes:
            if t <= self.t < t + 0.35:
                u = (self.t - t) / 0.35
                return (1 - u) * (0.6 + 0.4 * math.sin(u * 40) ** 2)
        return 0.0


def act(run: Run, port: int) -> None:
    pass


# --- the reference pilot -------------------------------------------------------

def _choose(run: Run, want: Vec) -> Optional[int]:
    """The one port that pushes most like *want* (an acceleration)."""
    f, r = run.frame()
    a, b = dot(want, f), dot(want, r)
    h = math.hypot(a, b)
    if abs(want[1]) > max(0.8, h * 0.9):
        return UP if want[1] > 0 else DOWN
    if h < 0.6:
        return None
    best, score = None, -1e9
    for port, (pa, pb, _pc) in PUSH.items():
        if port in (UP, DOWN):
            continue
        s = (pa * a + pb * b) / math.hypot(pa, pb)
        if s > score:
            best, score = port, s
    return best


def autopilot(run: Run) -> List[int]:
    """Line up on the next hoop's axis from the near side, then go
    through, one port a step."""
    if run.result is not None or run.next >= len(run.course.hoops):
        return []
    level = run.level
    h = run.course.hoops[run.next]
    c, n = hoop_at(h, run.t)
    q = sub(run.p, c)
    along = dot(q, n)
    side = 1.0 if along > 0 else -1.0
    off = sub(q, scale(n, along))
    lined = norm(off) < 0.42 * h.radius
    if lined and abs(along) < 4.5:
        aim, speed = -side * 3.0, 5.5
    else:
        aim, speed = side * 3.5, 8.0

    def spot(t: float) -> Vec:
        cc, nn = hoop_at(h, t)
        return add(cc, scale(nn, aim))

    target = spot(run.t)
    drift = scale(sub(spot(run.t + 0.1), target), 10.0)
    top = ACC / level.drag
    want_v = sub(target, run.p)
    d = norm(want_v)
    want_v = add(scale(unit(want_v), min(speed, top * 0.8, 2.0 * d)), drift)
    need = scale(sub(want_v, run.v), 5.0)
    gust = gust_at(run.course, run.t)
    if gust is not None:
        need = sub(need, (math.sin(gust.heading) * gust.strength, 0.0,
                          math.cos(gust.heading) * gust.strength))
    port = _choose(run, need)
    return [] if port is None else [port]


def play(course: Course, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    """Fly *course* with *pilot*, one port a step as the agent has."""
    run = Run(course)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
