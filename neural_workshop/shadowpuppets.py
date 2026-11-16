# -*- coding: utf-8 -*-
"""Shadow Puppets: turn the thing until its shadow is the shape asked.

A lamp throws the shadow of a block figure on the wall. Drag to turn
the figure (across spins it, up and down tips it) and roll it on the
keys (Q and E). Bring its shadow to the shape asked for and keep it
there a moment.

The ladder:

* rungs 1-3: a flat figure, the wanted shadow drawn on the wall under
  the real one, and a tone that rises as you near it;
* rungs 4-6: a figure with a different shape from every side;
* rungs 7-9: the wanted shadow is on a card, not on the wall;
* rungs 10-12: two shadows one after the other, no tone;
* rungs 13-15: the shape is only named;
* rungs 16-19: the figure is behind the screen: you see its shadow
  alone;
* from rung 20: three shadows and more, a finer fit every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import FrozenSet, List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

ROLL_LEFT, ROLL_RIGHT = H.KEYS, H.KEYS + 1
PORTS = H.KEYS + 2
EVENTS = tuple(range(PORTS))
GAIN = 0.3                    # degrees a unit of drag
ROLL = 2.0                    # degrees a tap
STAY = 0.7                    # seconds the shadow must hold
WARM, DONE, TICK, HUM = range(4)
PATCHES = ('glass', 'bell', 'wood', 'pad')
SHAPES = {
    'L': ('X..', 'X..', 'XXX'), 'T': ('XXX', '.X.', '.X.'),
    'I': ('.X.', '.X.', '.X.'), 'C': ('XXX', 'X..', 'XXX'),
    'S': ('.XX', '.X.', 'XX.'), '+': ('.X.', 'XXX', '.X.'),
    'O': ('XXX', 'X.X', 'XXX'), 'U': ('X.X', 'X.X', 'XXX'),
    'H': ('X.X', 'XXX', 'X.X'),
}
Mat = Tuple[Tuple[float, float, float], ...]
EYE: Mat = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def mul(a: Mat, b: Mat) -> Mat:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                       for j in range(3)) for i in range(3))


def turn(axis: int, degrees: float) -> Mat:
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m = [[1.0 if r == k else 0.0 for k in range(3)] for r in range(3)]
    m[i][i], m[i][j], m[j][i], m[j][j] = c, -s, s, c
    return tuple(tuple(r) for r in m)


def put(m: Mat, v) -> Tuple[float, float, float]:
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def apart(a: Mat, b: Mat) -> float:
    """Degrees between two ways of standing."""
    trace = sum(a[i][k] * b[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1) / 2))))


def _squares() -> Tuple[Mat, ...]:
    def snap(m):
        return tuple(tuple(float(round(v)) for v in r) for r in m)
    seen, todo = {EYE}, [EYE]
    while todo:
        m = todo.pop()
        for axis in range(3):
            n = snap(mul(turn(axis, 90.0), m))
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return tuple(sorted(seen))


SQUARE = _squares()           # the 24 ways a cube can sit


def cells(name: str) -> FrozenSet[Tuple[int, int]]:
    rows = SHAPES[name]
    return frozenset((x - 1, 1 - y) for y in range(3) for x in range(3)
                     if rows[y][x] == 'X')


def blocks(front: str, side: str) -> Tuple[Tuple[int, int, int], ...]:
    a, b = cells(front), cells(side)
    return tuple(sorted((x, y, z) for x, y in a for z, y2 in b if y == y2))


def shadow(cubes, m: Mat) -> FrozenSet[Tuple[int, int]]:
    out = set()
    for c in cubes:
        x, y, _z = put(m, c)
        out.add((int(round(x)), int(round(y))))
    return frozenset(out)


class Grade(NamedTuple):
    rung: int
    flat: bool
    shadows: int               # how many to cast in turn
    near: float                # degrees it may be off
    shown: str                 # 'wall', 'card' or 'named'
    tone: bool
    hidden: bool               # the figure is behind the screen
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    shadows = 1 if r < 10 else 2 if r < 20 else min(8, 3 + top // 8)
    return Grade(
        rung=r, flat=r < 4, shadows=shadows,
        near=(16.0 if r < 7 else 13.0 if r < 13 else 11.0 if r < 20
              else max(4.0, 10.0 - 0.15 * top)),
        shown='wall' if r < 7 else 'card' if r < 13 else 'named',
        tone=r < 10, hidden=r >= 16,
        seconds=20.0 + 30.0 * shadows)


class Puppet(NamedTuple):
    level: Grade
    front: str
    side: str
    start: Mat
    wanted: Tuple[FrozenSet[Tuple[int, int]], ...]
    names: Tuple[str, ...]     # what each is called, where it has a name
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Puppet]:
    names = sorted(SHAPES)
    front = draw.choice([n for n in names if n != 'I'])
    side = 'I' if level.flat else draw.choice(
        [n for n in names if n not in (front, 'I')])
    cubes = blocks(front, side)
    seen = {}
    for q in SQUARE:
        seen.setdefault(shadow(cubes, q), q)
    if level.shown == 'named':
        named = [(cells(n), n) for n in (front, side) if n != 'I'
                 and cells(n) in seen]
        draw.shuffle(named)
        picks = named[:level.shadows]
        while len(picks) < level.shadows:      # then back and forth
            picks.append(picks[len(picks) % max(1, len(named))]
                         if len(named) > 1 else None)
        if None in picks or any(picks[i][0] == picks[i + 1][0]
                                for i in range(len(picks) - 1)):
            return None
    else:
        kinds = sorted(seen, key=sorted)
        picks, last = [], None
        for _i in range(level.shadows):
            rest = [k for k in kinds if k != last and len(k) >= 4]
            if not rest:
                return None
            last = draw.choice(rest)
            picks.append((last, ''))
    first = picks[0][0]
    away = [q for q in SQUARE if shadow(cubes, q) != first]
    if not away:
        return None
    start = draw.choice(away)
    for axis in range(3):
        start = mul(turn(axis, draw.uniform(-12.0, 12.0)), start)
    return Puppet(level, front, side, start, tuple(p[0] for p in picks),
                  tuple(p[1] for p in picks), draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Puppet:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


class Run(H.HandRun):
    def __init__(self, puppet: Puppet) -> None:
        super().__init__(puppet.level.seconds)
        self.puppet, self.level = puppet, puppet.level
        self.cubes = blocks(puppet.front, puppet.side)
        self.m: Mat = puppet.start
        self.at = 0                    # which shadow is wanted
        self.stay = 0.0
        self.last = (self.hand.x, self.hand.y)
        self.tone_at = 0.5
        self.fits = [tuple(q for q in SQUARE if shadow(self.cubes, q) == w)
                     for w in puppet.wanted]

    def wanted(self) -> FrozenSet[Tuple[int, int]]:
        return self.puppet.wanted[min(self.at, len(self.fits) - 1)]

    def name(self) -> str:
        return self.puppet.names[min(self.at, len(self.fits) - 1)]

    def nearest(self) -> Tuple[float, Mat]:
        return min(((apart(self.m, q), q)
                    for q in self.fits[min(self.at, len(self.fits) - 1)]),
                   key=lambda p: p[0])

    def off(self) -> float:
        return self.nearest()[0]

    def press(self) -> None:
        self.hand.down = True
        self.last = (self.hand.x, self.hand.y)

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if port in (ROLL_LEFT, ROLL_RIGHT):
            self.m = mul(turn(2, ROLL if port == ROLL_LEFT else -ROLL),
                         self.m)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.hand.down:
            dx = self.hand.x - self.last[0]
            dy = self.hand.y - self.last[1]
            if dx or dy:
                self.m = mul(turn(0, -dy * GAIN),
                             mul(turn(1, dx * GAIN), self.m))
        self.last = (self.hand.x, self.hand.y)
        off = self.off()
        if self.level.tone and self.t >= self.tone_at:
            self.tone_at = self.t + 0.35
            self.note(0.12, 220.0 * 2 ** (2.0 * (1 - min(off, 180.0)
                                                 / 180.0)), WARM, 0.3)
        if off <= self.level.near:
            self.stay += dt
            if self.stay >= STAY:
                self.at += 1
                self.stay = 0.0
                self.note(0.5, 880.0, DONE, 0.55)
                if self.at >= len(self.fits):
                    self.result = (True, _('Every shadow cast'))
                    return
        else:
            self.stay = 0.0
        if self.t >= self.end:
            self.result = (False, _('Time: %d of %d cast')
                           % (self.at, len(self.fits)))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Take whichever single move brings the figure nearest the fit."""
    if run.result is not None:
        return []
    off, fit = run.nearest()
    if off <= 0.5 * run.level.near:
        return []
    hand = run.hand
    if not hand.down:
        if abs(hand.x - 500) > 150 or abs(hand.y - 320) > 120:
            move = H.toward(hand, 500.0, 320.0, tol=40.0)
            if move is not None:
                return [move]
        return [H.PRESS]
    if not (100 < hand.x < 900 and 80 < hand.y < 560):
        return [H.RELEASE]
    best = (off, None)
    for port in range(12):
        d, size = H.DIRS[port // 3], H.STEPS[port % 3]
        m = mul(turn(0, -d[1] * size * GAIN),
                mul(turn(1, d[0] * size * GAIN), run.m))
        gap = apart(m, fit)
        if gap < best[0] - 1e-6:
            best = (gap, port)
    for port in (ROLL_LEFT, ROLL_RIGHT):
        m = mul(turn(2, ROLL if port == ROLL_LEFT else -ROLL), run.m)
        gap = apart(m, fit)
        if gap < best[0] - 1e-6:
            best = (gap, port)
    return [best[1]] if best[1] is not None else []


def play(puppet: Puppet, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(puppet), pilot, EVENTS, act, dt)
