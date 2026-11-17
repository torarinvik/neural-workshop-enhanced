# -*- coding: utf-8 -*-
"""Claw Machine: get the claw over the gold prize, then drop it.

A glass cabinet seen from the front, prizes on its floor at different
depths, and a claw on a cable under a trolley. Move the trolley left
and right, in and out, then drop: the claw goes straight down and
closes. It has to come down close over the gold prize -- left and right
are easy to see from the front; how far in is the whole difficulty.

* rung 1: a side view of the cabinet is shown as well, and the claw's
  shadow lies on the floor under it;
* rungs 2-3: no side view; the shadow still there;
* rungs 4-6: no shadow either: depth only from perspective -- how big
  things look, where they stand on the floor;
* rungs 7-9: the claw swings on its cable when the trolley moves and
  stops; drop when it has settled, or time the swing;
* rungs 10-12: the camera stands lower, so depth is squeezed, and the
  prizes come in different sizes, so a small near one and a big far
  one look alike;
* rungs 13 and up: the floor moves, carrying the prizes along; the
  claw swings more freely and the allowance shrinks every rung.

For the agent boundary: ports 0-3 move the trolley left, right, in
and out, for the step they are sent in; port 4 drops the claw.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

LEFT, RIGHT, IN, OUT, DROP = range(5)
PORTS = 5
EVENTS = (DROP,)
HALF = 1.0                     # the floor is x in [-HALF, HALF]
DEEP = 1.6                     # and z in [0, DEEP], 0 at the glass
TOP = 1.7                      # the trolley's height
SPEED = 0.55                   # the trolley, units a second
FALL = 1.1                     # the claw drops this fast
G_OVER_L = 16.0                # the cable's pendulum stiffness
PATCHES = ('wood', 'bell', 'growl')
COLOURS = ((230, 80, 80), (80, 140, 230), (120, 200, 120), (200, 120, 220),
           (240, 150, 60))


class Grade(NamedTuple):
    rung: int
    side: bool
    shadow: bool
    swing: float               # damping of the swing: lower swings longer
    low: bool                  # the camera stands low
    sizes: bool                # prizes of different sizes
    belt: float                # the floor's speed
    tol: float                 # how close over the prize the claw must come
    prizes: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, True, True, 0.0, False, False, 0.0, 0.16, 5)
    if r < 4:
        return Grade(r, False, True, 0.0, False, False, 0.0, 0.13, 6)
    if r < 7:
        return Grade(r, False, False, 0.0, False, False, 0.0, 0.11, 7)
    if r < 10:
        return Grade(r, False, False, 0.9, False, False, 0.0, 0.1, 7)
    if r < 13:
        return Grade(r, False, False, 0.7, True, True, 0.0, 0.09, 8)
    return Grade(r, False, False, max(0.25, 0.6 - 0.03 * (r - 13)), True,
                 True, min(0.25, 0.06 + 0.01 * (r - 13)),
                 max(0.035, 0.085 * 0.94 ** (r - 13)), 8)


class Prize(NamedTuple):
    x: float
    z: float
    r: float
    colour: Tuple[int, int, int]


class Cabinet(NamedTuple):
    level: Grade
    prizes: Tuple[Prize, ...]      # the first is the gold one
    start: Tuple[float, float]
    seconds: float


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Cabinet:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(200):
        prizes: List[Prize] = []
        while len(prizes) < level.prizes:
            r = draw.uniform(0.1, 0.24) if level.sizes else 0.16
            x = draw.uniform(-HALF + 0.25, HALF - 0.25)
            z = draw.uniform(0.25, DEEP - 0.25)
            if all(math.hypot(x - p.x, z - p.z) > r + p.r + 0.05
                   for p in prizes):
                colour = (250, 205, 60) if not prizes else \
                    COLOURS[len(prizes) % len(COLOURS)]
                prizes.append(Prize(x, z, r, colour))
        start = (draw.choice((-1, 1)) * (HALF - 0.1),
                 draw.choice((0.1, DEEP - 0.1)))
        gold = prizes[0]
        if math.hypot(start[0] - gold.x, start[1] - gold.z) < 0.6:
            continue
        cab = Cabinet(level, tuple(prizes), start, 40.0)
        if play(cab)[0]:
            return cab
    raise RuntimeError('claw machine: no cabinet for rung %d' % rung)


class Run(object):
    def __init__(self, cab: Cabinet) -> None:
        self.cab = cab
        self.level = cab.level
        self.t = 0.0
        self.x, self.z = cab.start
        self.vx = self.vz = 0.0
        self.ox = self.oz = 0.0          # the claw's swing off the trolley
        self.wx = self.wz = 0.0
        self.drop: Optional[float] = None
        self.depth = 0.0                 # how far the claw has come down
        self.belt = 0.0                  # how far the floor has moved
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = cab.seconds

    def prize_at(self, p: Prize, t: Optional[float] = None
                 ) -> Tuple[float, float]:
        """Where a prize is, the floor carrying it round."""
        s = self.belt if t is None else self.level.belt * t
        x = (p.x + s + HALF) % (2 * HALF) - HALF
        return x, p.z

    def claw(self) -> Tuple[float, float]:
        return self.x + self.ox, self.z + self.oz

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        self.belt += self.level.belt * dt
        on = {control} if isinstance(control, int) else set(control or ())
        vx = vz = 0.0
        if self.drop is None:
            vx = SPEED * ((RIGHT in on) - (LEFT in on))
            vz = SPEED * ((IN in on) - (OUT in on))
        nx = max(-HALF, min(HALF, self.x + vx * dt))
        nz = max(0.0, min(DEEP, self.z + vz * dt))
        ax, az = ((nx - self.x) / dt - self.vx) / dt, \
            ((nz - self.z) / dt - self.vz) / dt
        self.vx, self.vz = (nx - self.x) / dt, (nz - self.z) / dt
        self.x, self.z = nx, nz
        if self.level.swing:
            c = self.level.swing
            for axis, acc in (('x', ax), ('z', az)):
                o, w = getattr(self, 'o' + axis), getattr(self, 'w' + axis)
                w += (-G_OVER_L * o - c * w - 0.06 * acc) * dt
                o += w * dt
                setattr(self, 'o' + axis, max(-0.3, min(0.3, o)))
                setattr(self, 'w' + axis, w)
        if self.drop is not None:
            self.depth += FALL * dt
            if self.depth >= TOP - 0.25:
                self._close()
        elif self.t > self.cab.seconds:
            self.result = (False, _('Out of time'))

    def let_go(self) -> None:
        if self.result is None and self.drop is None:
            self.drop = self.t
            self._note(0.15, 300.0, 0, 0.3)

    def _close(self) -> None:
        cx, cz = self.claw()
        best, which = None, None
        for k, p in enumerate(self.cab.prizes):
            px, pz = self.prize_at(p)
            d = math.hypot(px - cx, pz - cz)
            if d <= self.level.tol + (p.r - 0.16) * 0.5 and \
                    (best is None or d < best):
                best, which = d, k
        gx, gz = self.prize_at(self.cab.prizes[0])
        if which == 0:
            self.result = (True, _('Got it'))
            self._note(0.3, 1320.0, 1, 0.3)
        elif which is not None:
            self.result = (False, _('That is not the gold one'))
            self._note(0.4, 110.0, 2, 0.4)
        else:
            dx, dz = cx - gx, cz - gz
            where = _('too far in') if dz > abs(dx) else \
                _('not far enough in') if -dz > abs(dx) else \
                _('to the right') if dx > 0 else _('to the left')
            self.result = (False, _('Missed: %s') % where)
            self._note(0.4, 110.0, 2, 0.4)


def act(run: Run, port: int) -> None:
    if port == DROP:
        run.let_go()


def autopilot(run: Run) -> List[int]:
    """Knows where the gold prize is: goes over it -- where it will be
    when the claw comes down -- waits for the swing to settle, drops."""
    if run.result is not None or run.drop is not None:
        return []
    fall = (TOP - 0.25) / FALL
    gold = run.cab.prizes[0]
    gx, gz = run.prize_at(gold, None)
    gx = (gx + run.level.belt * fall + HALF) % (2 * HALF) - HALF
    dx, dz = gx - run.x, gz - run.z
    step = SPEED / 30.0
    tol = run.level.tol * 0.35
    if abs(dx) > max(tol, step) and abs(dx) >= abs(dz):
        return [RIGHT if dx > 0 else LEFT]
    if abs(dz) > max(tol, step):
        return [IN if dz > 0 else OUT]
    if run.level.swing:
        # the swing's whole size, now and over the drop
        amp = math.hypot(run.ox, run.oz) + math.hypot(
            run.wx, run.wz) / math.sqrt(G_OVER_L)
        if amp > tol:
            return []
    if run.level.belt and (abs(dx) > tol or abs(dz) > tol):
        return []
    return [DROP]


def play(cab: Cabinet, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(cab)
    while run.result is None:
        ports = pilot(run)
        held = [p for p in ports if p not in EVENTS]
        for p in ports:
            if p in EVENTS:
                act(run, p)
        run.step(dt, held[0] if held else None)
    return run.result
