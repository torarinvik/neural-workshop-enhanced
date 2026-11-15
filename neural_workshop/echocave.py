# -*- coding: utf-8 -*-
"""Echo Cave: fly a bat down a winding cave, by sight and then by ear.

A bat flies on down a cave that winds left and right, up and down,
widening and narrowing. Steer it -- with the mouse, which it flies
toward, or the arrow keys -- and keep it off the rock. Moths flutter in
the cave, each buzzing from where it is; fly through them to catch
them. Space clicks: the click comes back off the rock around, sooner
and louder from the side that is near, higher from above and lower from
below, and a long low echo from far down the cave says which way it
turns.

At first the cave is lit. Up the ladder the light fails, until the
clicks and the moths' buzzing are all there is to fly by.

The ladder:

* rungs 1-3: a lit, wide cave with gentle bends, three moths: catch one;
* rungs 4-6: dimmer -- only the near cave shows -- and tighter bends,
  four moths: catch two;
* rungs 7-9: dark: only a click lights the cave, for a moment;
* rungs 10-12: the moths can only be heard;
* rungs 13-15: narrower and faster, bending both ways at once;
* rungs 16-19: no light at all -- fly by the echoes alone;
* from rung 20: narrower and faster every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Set, Tuple

from .drshape import Note
from .i18n import _

UP, DOWN, LEFT, RIGHT, UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT, CLICK = \
    range(9)
PORTS = 9
EVENTS = (CLICK,)
#: Each steering port's push (x, y).
PUSHES = {UP: (0, 1), DOWN: (0, -1), LEFT: (-1, 0), RIGHT: (1, 0),
          UP_LEFT: (-0.71, 0.71), UP_RIGHT: (0.71, 0.71),
          DOWN_LEFT: (-0.71, -0.71), DOWN_RIGHT: (0.71, -0.71)}
BODY = 0.6                     # the bat's half size
PUSH = 34.0                    # steering acceleration
DAMP = 2.6
CATCH = 1.6                    # how near a moth must pass
AHEAD = 5.0                    # the slice a click sounds out
FAR = 22.0                     # how far the long echo reaches
SOUND = 0.012                  # seconds of echo delay a unit of distance
DIRECTIONS = 8
# The patches a run's notes use, by index.
P_CLICK, P_ECHO, P_FAR, P_MOTH = range(4)
PATCHES = ('wood', 'glass', 'pad', 'chirp')


class Grade(NamedTuple):
    rung: int
    radius: float
    bend: float                # how far the cave wanders, units
    both: bool                 # wanders up and down as much as sideways
    speed: float
    length: float
    moths: int
    need: int
    see: float                 # how far the cave is lit
    flash: float               # how far a click lights it (0: never)
    moths_seen: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        radius=(7.0 if r < 4 else 6.0 if r < 13 else 5.2 if r < 20
                else max(4.4, 5.0 - 0.04 * top)),
        bend=4.0 if r < 4 else 6.0 if r < 13 else 7.5,
        both=r >= 13,
        speed=(11.0 if r < 4 else 13.0 if r < 13 else 15.0 if r < 20
               else min(19.0, 15.5 + 0.25 * top)),
        length=240.0 if r < 13 else 300.0,
        moths=3 if r < 4 else 4,
        need=1 if r < 4 else 2,
        see=60.0 if r < 4 else 22.0 if r < 7 else 0.0,
        flash=0.0 if r < 7 or r >= 16 else 40.0,
        moths_seen=r < 10)


class Cave(NamedTuple):
    level: Grade
    waves: Tuple[Tuple[float, float, float], ...]   # x: amp, wavelength, phase
    waves_y: Tuple[Tuple[float, float, float], ...]
    width: Tuple[float, float]                       # radius wave: wl, phase
    moths: List[Tuple[float, float, float]]          # z, dx, dy from the axis
    flutter: int


def axis(cave: Cave, z: float) -> Tuple[float, float]:
    """The middle of the cave at depth *z*."""
    ramp = min(1.0, z / 30.0)            # straight at the mouth
    x = sum(a * math.sin(z / w + p) for a, w, p in cave.waves)
    y = sum(a * math.sin(z / w + p) for a, w, p in cave.waves_y)
    return x * ramp, y * ramp


def radius(cave: Cave, z: float) -> float:
    wl, ph = cave.width
    return cave.level.radius * (1.0 + 0.18 * math.sin(z / wl + ph))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Cave:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        cave = _build(level, draw)
        best = best or cave
        if play(cave)[0] and not play(cave, lambda run: [])[0]:
            return cave
    return best


def _build(level: Grade, draw: random.Random) -> Cave:
    b = level.bend
    waves = ((b * 0.7, draw.uniform(9, 13), draw.uniform(0, 6.3)),
             (b * 0.3, draw.uniform(4.5, 6.5), draw.uniform(0, 6.3)))
    up = b if level.both else b * 0.45
    waves_y = ((up * 0.7, draw.uniform(10, 15), draw.uniform(0, 6.3)),
               (up * 0.3, draw.uniform(5, 7), draw.uniform(0, 6.3)))
    width = (draw.uniform(7, 11), draw.uniform(0, 6.3))
    moths = []
    gap = (level.length - 60.0) / level.moths
    for k in range(level.moths):
        z = 45.0 + gap * (k + draw.uniform(0.2, 0.8))
        a = draw.uniform(0, 2 * math.pi)
        d = draw.uniform(0.15, 0.5) * level.radius
        moths.append((z, d * math.cos(a), d * math.sin(a)))
    return Cave(level, waves, waves_y, width, moths, draw.randrange(1000))


def _on(control) -> Set[int]:
    if control is None:
        return set()
    if isinstance(control, int):
        return {control}
    return set(control)


class Run:
    def __init__(self, cave: Cave) -> None:
        self.cave = cave
        self.level = cave.level
        self.t = 0.0
        self.z = 0.0
        self.x, self.y = axis(cave, 0.0)
        self.vx = self.vy = 0.0
        #: Where the mouse wants the bat, relative to it, or None.
        self.aim: Optional[Tuple[float, float]] = None
        self.caught = [False] * len(cave.moths)
        self.clicks: List[float] = []
        self.notes: List[Note] = []
        self.next_buzz = 0.0
        self.seed = 0
        self.result: Optional[Tuple[bool, str]] = None

    def moth(self, k: int, t: Optional[float] = None
             ) -> Tuple[float, float, float]:
        """Moth *k* where it flutters at time *t* (x, y, z)."""
        t = self.t if t is None else t
        z, dx, dy = self.cave.moths[k]
        cx, cy = axis(self.cave, z)
        f = self.cave.flutter + k * 7
        return (cx + dx + 0.6 * math.sin(2.1 * t + f),
                cy + dy + 0.5 * math.sin(2.7 * t + f * 1.3), z)

    def lit(self) -> float:
        """How far ahead the cave can be seen just now."""
        see = self.level.see
        if self.level.flash and self.clicks:
            ago = self.t - self.clicks[-1]
            if ago < 0.4:
                see = max(see, self.level.flash * (1 - ago / 0.4))
        return see

    def click(self) -> None:
        if self.result is not None:
            return
        if self.clicks and self.t - self.clicks[-1] < 0.15:
            return
        self.clicks.append(self.t)
        self.clicks = self.clicks[-8:]
        self._echoes()

    def wall_distance(self, ux: float, uy: float, z: float) -> float:
        """From the bat along (ux, uy) to the rock, in the slice at *z*."""
        cx, cy = axis(self.cave, z)
        r = radius(self.cave, z)
        px, py = self.x - cx, self.y - cy
        b = px * ux + py * uy
        c = px * px + py * py - r * r
        disc = b * b - c
        return max(0.0, -b + math.sqrt(max(0.0, disc)))

    def _echoes(self) -> None:
        t = self.t
        self.seed += 1
        out = [Note(t, 0.03, 2400.0, 0.0, 0.0, 0.5, 0.5, 1.0, P_CLICK,
                    self.seed, -1, 0.0)]
        for k in range(DIRECTIONS):
            a = 2 * math.pi * k / DIRECTIONS
            ux, uy = math.cos(a), math.sin(a)
            d = self.wall_distance(ux, uy, self.z + AHEAD)
            self.seed += 1
            g = 0.55 / (1.0 + 0.35 * d)
            out.append(Note(t + 0.02 + 2 * d * SOUND, 0.05,
                            1200.0 * 2 ** (0.6 * uy), ux, ux, g, g, 0.9,
                            P_ECHO, self.seed, -1, 0.0))
        fx, fy = axis(self.cave, self.z + FAR)
        dx = max(-1.0, min(1.0, (fx - self.x) / (2 * self.level.radius)))
        dy = max(-1.0, min(1.0, (fy - self.y) / (2 * self.level.radius)))
        self.seed += 1
        out.append(Note(t + 2 * FAR * SOUND, 0.25, 260.0 * 2 ** (0.7 * dy),
                        dx, dx, 0.3, 0.3, 0.5, P_FAR, self.seed, -1, 0.0))
        out.sort(key=lambda n: n.t)
        self.notes.extend(out)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        level = self.level
        self.t += dt
        on = _on(control)
        ax = sum(PUSHES[p][0] for p in on if p in PUSHES)
        ay = sum(PUSHES[p][1] for p in on if p in PUSHES)
        d = math.hypot(ax, ay)
        if d > 1.0:
            ax, ay = ax / d, ay / d
        if not (ax or ay) and self.aim is not None:
            mx, my = self.aim
            d = math.hypot(mx, my)
            if d > 0.2:
                k = min(1.0, d / 3.0) / d
                ax, ay = mx * k, my * k
        self.vx += (PUSH * ax - DAMP * self.vx) * dt
        self.vy += (PUSH * ay - DAMP * self.vy) * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        z0 = self.z
        self.z += level.speed * dt
        for k in range(len(self.caught)):
            mx, my, mz = self.moth(k)
            if not self.caught[k] and z0 < mz <= self.z and \
                    math.hypot(mx - self.x, my - self.y) < CATCH:
                self.caught[k] = True
                self.seed += 1
                self.notes.append(Note(self.t, 0.12, 1500.0, 0.0, 0.0, 0.4,
                                       0.4, 1.0, P_ECHO, self.seed, -1, 0.0))
        self._buzz()
        cx, cy = axis(self.cave, self.z)
        if math.hypot(self.x - cx, self.y - cy) > radius(self.cave, self.z) \
                - BODY:
            self.result = (False, _('Hit the rock'))
            return
        if self.z >= level.length:
            got = sum(self.caught)
            if got >= level.need:
                self.result = (True, _('Out of the cave, %d moths caught')
                               % got)
            else:
                self.result = (False, _('Out of the cave, but only %d of %d '
                                        'moths caught') % (got, level.need))

    def _buzz(self) -> None:
        while self.next_buzz <= self.t:
            t = self.next_buzz
            self.next_buzz += 0.12
            for k in range(len(self.caught)):
                if self.caught[k]:
                    continue
                mx, my, mz = self.moth(k, t)
                dz = mz - self.z
                if not -3.0 < dz < 40.0:
                    continue
                pan = max(-1.0, min(1.0, (mx - self.x) / 5.0))
                g = 0.3 / (1.0 + max(0.0, dz) / 8.0)
                self.seed += 1
                f = 520.0 * 2 ** (max(-1.0, min(1.0, (my - self.y) / 5.0))
                                  * 0.7)
                self.notes.append(Note(t, 0.1, f, pan, pan, g, g, 0.7,
                                       P_MOTH, self.seed, -1, 0.0))


def act(run: Run, port: int) -> None:
    if port == CLICK:
        run.click()


def autopilot(run: Run) -> List[int]:
    """Steer for where the cave's middle (or, while more are needed, the
    next moth) will be a moment from now; click twice a second."""
    level = run.level
    look = 0.35
    tz = run.z + level.speed * look
    tx, ty = axis(run.cave, tz)
    for k in range(len(run.caught)):
        if run.caught[k] or sum(run.caught) >= level.need:
            continue
        mx, my, mz = run.moth(k, run.t + look)
        if 0 < mz - run.z < level.speed * 1.4:
            cx, cy = axis(run.cave, mz)
            safe = radius(run.cave, mz) - BODY - 1.0
            if math.hypot(mx - cx, my - cy) < safe:
                tx, ty = mx, my
            break
    out = []
    wx = (tx - run.x) * 3.0 - run.vx * 1.0
    wy = (ty - run.y) * 3.0 - run.vy * 1.0
    if math.hypot(wx, wy) > 0.5:
        a = math.atan2(wy, wx)
        out.append(min(PUSHES, key=lambda p: -math.cos(
            a - math.atan2(PUSHES[p][1], PUSHES[p][0]))))
    if not run.clicks or run.t - run.clicks[-1] > 0.5:
        out.append(CLICK)
    return out


def play(cave: Cave, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(cave)
    while run.result is None:
        ports = pilot(run)
        for port in ports:
            if port in EVENTS:
                act(run, port)
        run.step(dt, [p for p in ports if p not in EVENTS])
    return run.result
