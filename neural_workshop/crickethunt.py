# -*- coding: utf-8 -*-
"""Cricket Hunt: find the cricket in the dark by its chirping.

A dark room, seen from inside: walls, floor, a table and shelves just
visible, and somewhere a cricket, too small and dark to see. It chirps.
The ear tells where: louder nearer, in the ear on its side, duller when
it is behind, and louder and brighter the more directly you look at it
-- so turning the head, and looking up and down, homes in on it. Look
straight at it from within two metres and catch it.

* rung 1: a small room, one cricket at the height of the table,
  chirping steadily;
* rungs 2-3: a bigger room, the cricket anywhere from knee to chest
  height;
* rungs 4-6: two crickets, from the floor to the top shelf;
* rungs 7-9: chirps further apart, a hum in the room, up to three;
* rungs 10 and up: a cricket hops somewhere else when you come near;
  more crickets, bigger rooms, longer silences and more hum, without
  end.

Three grabs at nothing end the try.

For the agent boundary: ports 0-5 walk forward and back, turn left and
right, and look up and down, for the step they are sent in; port 6
grabs. The chirps are on the audio channel.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import livesound as LS
from .drshape import Note
from .i18n import _

FORWARD, BACK, LEFT, RIGHT, UP, DOWN, GRAB = range(7)
PORTS = 7
EVENTS = (GRAB,)
EYE = 1.6
WALK = 1.3                     # metres a second
TURN = math.radians(90)        # a second
TILT = math.radians(60)
REACH = 2.0                    # metres
MISSES = 3
PATCHES = ('wood', 'bell', 'growl')


class Grade(NamedTuple):
    rung: int
    room: float                # metres a side
    crickets: int
    low: float                 # heights they sit at
    high: float
    every: float               # seconds from one chirp to the next
    hum: float
    hop: bool
    radius: float              # how close the look must pass


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, 6.0, 1, 0.75, 0.75, 0.6, 0.0, False, 0.55)
    if r < 4:
        return Grade(r, 7.0, 1, 0.4, 1.4, 0.7, 0.0, False, 0.5)
    if r < 7:
        return Grade(r, 8.0, 2, 0.0, 2.2, 0.8, 0.0, False, 0.45)
    if r < 10:
        return Grade(r, 9.0, 2 + (r >= 8), 0.0, 2.2, 1.4, 0.04, False, 0.4)
    return Grade(r, min(16.0, 10.0 + 0.4 * (r - 10)),
                 min(6, 3 + (r - 10) // 3), 0.0, 2.4,
                 min(4.0, 1.5 + 0.12 * (r - 10)),
                 min(0.2, 0.05 + 0.01 * (r - 10)), True, 0.4)


class Cricket(NamedTuple):
    at: Tuple[float, float, float]
    hop: Tuple[float, float, float]     # where it goes if it hops
    pitch: float
    phase: float


class Room(NamedTuple):
    level: Grade
    crickets: Tuple[Cricket, ...]
    start: Tuple[float, float, float]   # x, z, heading
    furniture: Tuple[Tuple[float, float, float, float, float], ...]
    seconds: float


def _spot(level: Grade, draw: random.Random) -> Tuple[float, float, float]:
    s = level.room
    return (draw.uniform(0.6, s - 0.6), draw.uniform(level.low, level.high),
            draw.uniform(0.6, s - 0.6))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Room:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    s = level.room
    for _k in range(100):
        start = (s / 2, s / 2, draw.uniform(0, 2 * math.pi))
        cr = []
        for _c in range(level.crickets):
            at = _spot(level, draw)
            cr.append(Cricket(at, _spot(level, draw),
                              draw.uniform(2600, 3400), draw.uniform(0, 1)))
        # none right where you start, none on top of another
        if any(math.hypot(c.at[0] - start[0], c.at[2] - start[1]) < 2.0
               for c in cr):
            continue
        if any(math.hypot(a.at[0] - b.at[0], a.at[2] - b.at[2]) < 1.5
               for i, a in enumerate(cr) for b in cr[i + 1:]):
            continue
        furniture = ((0.3, 0.3, 1.6, 0.9, 0.75), (s - 2.0, 0.2, 1.8, 0.4, 2.2),
                     (0.2, s - 1.2, 0.4, 1.0, 1.8))
        room = Room(level, tuple(cr), start, furniture,
                    60.0 + 45.0 * level.crickets)
        if play(room)[0]:
            return room
    raise RuntimeError('cricket hunt: no room for rung %d' % rung)


def _look(yaw: float, pitch: float) -> Tuple[float, float, float]:
    return (math.sin(yaw) * math.cos(pitch), math.sin(pitch),
            math.cos(yaw) * math.cos(pitch))


class Run(object):
    def __init__(self, room: Room) -> None:
        self.room = room
        self.level = room.level
        self.t = 0.0
        self.x, self.z, self.yaw = room.start
        self.pitch = 0.0
        self.where = [c.at for c in room.crickets]
        self.hopped = [False] * len(room.crickets)
        self.caught = [False] * len(room.crickets)
        self.misses = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = room.seconds
        lv = self.level
        self.tracks = [LS.Track(((1, 1.0), (2, 0.35), (3, 0.15)),
                                gate=LS.Gate(32.0, 0.55, 0.22, lv.every,
                                             c.phase * lv.every))
                       for c in room.crickets]
        self.hum = LS.Track(((1, 1.0), (2, 0.5)), 0.4)
        self._sound()

    def eye(self) -> Tuple[float, float, float]:
        return self.x, EYE, self.z

    def heard(self, k: int) -> Tuple[float, float, float, float]:
        """Distance, side (-1 left, 1 right), how far ahead (-1 behind, 1
        in front) and how directly looked at (cosine) cricket *k* is."""
        ex, ey, ez = self.eye()
        cx, cy, cz = self.where[k]
        v = (cx - ex, cy - ey, cz - ez)
        r = math.sqrt(sum(a * a for a in v)) or 1e-6
        h = math.hypot(v[0], v[2]) or 1e-6
        az = math.atan2(v[0], v[2]) - self.yaw
        lk = _look(self.yaw, self.pitch)
        facing = sum(a * b for a, b in zip(lk, v)) / r
        return r, math.sin(az) * h / r, math.cos(az) * h / r, facing

    def _sound(self) -> None:
        for k, tr in enumerate(self.tracks):
            c = self.room.crickets[k]
            if self.caught[k] or self.result is not None:
                tr.set(self.t, c.pitch, 0.0, 0.0)
                continue
            r, side, ahead, facing = self.heard(k)
            g = 0.5 / (1.0 + r / 1.2) * (0.45 + 0.55 * max(0.0, facing) ** 2)
            bright = 0.25 + 0.75 * (ahead + 1) / 2
            tr.set(self.t, c.pitch, *LS.pan(g, side), bright=bright)
        h = self.level.hum if self.result is None else 0.0
        self.hum.set(self.t, 60.0, h, h)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        on = {control} if isinstance(control, int) else set(control or ())
        s = self.room.level.room
        move = WALK * dt * ((FORWARD in on) - 0.7 * (BACK in on))
        self.x = min(s - 0.3, max(0.3, self.x + math.sin(self.yaw) * move))
        self.z = min(s - 0.3, max(0.3, self.z + math.cos(self.yaw) * move))
        self.yaw += TURN * dt * ((RIGHT in on) - (LEFT in on))
        self.pitch = max(-1.35, min(1.35, self.pitch + TILT * dt *
                                    ((UP in on) - (DOWN in on))))
        if self.level.hop:
            for k, c in enumerate(self.room.crickets):
                if not self.hopped[k] and not self.caught[k] and \
                        math.hypot(self.where[k][0] - self.x,
                                   self.where[k][2] - self.z) < 2.0:
                    self.hopped[k] = True
                    self.where[k] = c.hop
                    self._note(0.05, 1800.0, 0, 0.15)
        if self.t > self.room.seconds:
            self.result = (False, _('%d of %d caught') % (
                sum(self.caught), len(self.caught)))
        self._sound()

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def aimed(self, k: int) -> bool:
        """Is cricket *k* within reach and right under the look?"""
        r, _s, _a, facing = self.heard(k)
        off = r * math.sqrt(max(0.0, 1 - min(1.0, facing) ** 2))
        return r <= REACH and facing > 0 and off <= self.level.radius

    def grab(self) -> None:
        if self.result is not None:
            return
        for k in range(len(self.caught)):
            if not self.caught[k] and self.aimed(k):
                self.caught[k] = True
                self._note(0.3, 1320.0, 1, 0.3)
                if all(self.caught):
                    self.result = (True, _('All %d caught in %.0f s') % (
                        len(self.caught), self.t))
                self._sound()
                return
        self.misses += 1
        self._note(0.25, 140.0, 2, 0.35)
        if self.misses >= MISSES:
            self.result = (False, _('Three grabs at nothing'))
            self._sound()


def act(run: Run, port: int) -> None:
    if port == GRAB:
        run.grab()


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def autopilot(run: Run) -> List[int]:
    """Knows where they are: turns to the nearest, walks up to it,
    looks at it, grabs."""
    if run.result is not None:
        return []
    left = [k for k in range(len(run.caught)) if not run.caught[k]]
    if not left:
        return []
    for k in left:
        if run.aimed(k):
            return [GRAB]
    k = min(left, key=lambda j: math.hypot(run.where[j][0] - run.x,
                                           run.where[j][2] - run.z))
    cx, cy, cz = run.where[k]
    dx, dz = cx - run.x, cz - run.z
    want = math.atan2(dx, dz)
    d = _wrap(want - run.yaw)
    if abs(d) > 0.06:
        return [RIGHT if d > 0 else LEFT]
    h = math.hypot(dx, dz)
    if h > 1.0:
        return [FORWARD]
    if h < 0.35:
        return [BACK]
    tilt = math.atan2(cy - EYE, h) - run.pitch
    if abs(tilt) > 0.05:
        return [UP if tilt > 0 else DOWN]
    return [FORWARD] if h > 0.6 else [BACK]


def mix(run: Run, t0: float, t1: float) -> bytes:
    return LS.mix(run.tracks + [run.hum], t0, t1, run.notes,
                  LS.make_patches(PATCHES))


def play(room: Room, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(room)
    run._sound = lambda: None
    while run.result is None:
        ports = pilot(run)
        held = [p for p in ports if p not in EVENTS]
        for p in ports:
            if p in EVENTS:
                act(run, p)
        run.step(dt, held[0] if held else None)
    return run.result
