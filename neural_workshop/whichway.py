# -*- coding: utf-8 -*-
"""Which Way: which way is the crowd of dots drifting?

A field of dots, each living a moment and then starting again
somewhere else. Some of them all move one way; the rest move every way.
Which way is the drift? No one dot tells: the answer is in the crowd.

The ladder:

* rungs 1-3: left or right; nine dots in ten drift together;
* rungs 4-6: half of them;
* rungs 7-9: four ways; a third;
* rungs 10-12: a quarter, and shorter lives;
* from rung 13: eight ways; the share falling toward one in sixteen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

DOTS = 120
SPEED = 0.22


class Grade(NamedTuple):
    rung: int
    ways: int
    together: float      # the share drifting together
    life: float          # seconds a dot lives
    show: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        ways=2 if r < 7 else 4 if r < 13 else 8,
        together=(0.9 if r < 4 else 0.5 if r < 7 else 0.33 if r < 10
                  else 0.25 if r < 13 else max(0.06, 0.2 * 0.93 ** (r - 13))),
        life=0.8 if r < 10 else 0.5,
        show=3.0)


def ways(n: int) -> Tuple[Tuple[str, float], ...]:
    out = [(_('Left'), math.pi), (_('Right'), 0.0)]
    if n >= 4:
        out += [(_('Up'), math.pi / 2), (_('Down'), -math.pi / 2)]
    if n >= 8:
        out += [(_('Up left'), 3 * math.pi / 4), (_('Up right'), math.pi / 4),
                (_('Down left'), -3 * math.pi / 4),
                (_('Down right'), -math.pi / 4)]
    return tuple(out)


class Puzzle(NamedTuple):
    level: Grade
    seed: int
    drift: float                 # radians
    phases: Tuple[float, ...]
    hue: float
    paper: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def dots(p: Puzzle, t: float) -> List[Tuple[float, float, float]]:
    """Every dot's place at time t, and the way it is going."""
    out = []
    together = int(round(DOTS * p.level.together))
    life = p.level.life
    for i, phase in enumerate(p.phases):
        age = (t + phase) % life
        born = S.stream(p.seed, i, int((t + phase) // life))
        x, y = born.random() * S.W, born.random()
        a = p.drift if i < together else born.uniform(0, 2 * math.pi)
        out.append(((x + math.cos(a) * SPEED * age) % S.W,
                    (y + math.sin(a) * SPEED * age) % 1.0, a))
    return out


def solve(p: Puzzle) -> int:
    # Where the crowd as a whole is going.
    sx = sy = 0.0
    for t in (0.3, 0.9, 1.5, 2.1):
        for _x, _y, a in dots(p, t):
            sx += math.cos(a)
            sy += math.sin(a)
    going = math.atan2(sy, sx)
    off = [abs((going - a + math.pi) % (2 * math.pi) - math.pi)
           for _name, a in ways(p.level.ways)]
    return off.index(min(off))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    table = ways(level.ways)
    for k in range(50):
        draw = random.Random(seed + k * 7919)
        answer = S.slot(seed, level.ways)
        p = Puzzle(level, seed + k, table[answer][1],
                   tuple(draw.random() * level.life for _i in range(DOTS)),
                   draw.random(), (26, 28, 36), 0.6, level.show + 6.0, (), (),
                   _('Which way are the dots drifting?'),
                   tuple(name for name, _a in table), answer)
        if solve(p) == answer:
            return p
    raise RuntimeError('no drift for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    if t < p.level.show and not judged:
        ink = S.hsv(p.hue, 0.15, 0.95)
        for x, y, _a in dots(p, t):
            out.append(S.disc(x, y, 0.009, ink))
    elif judged:
        cx, cy = S.W / 2, 0.5
        dx, dy = math.cos(p.drift) * 0.3, math.sin(p.drift) * 0.3
        gold = (250, 215, 80)
        out.append(S.line(cx - dx, cy - dy, cx + dx, cy + dy, 0.012, gold))
        for side in (-1, 1):
            a = p.drift + math.pi + side * 0.5
            out.append(S.line(cx + dx, cy + dy, cx + dx + math.cos(a) * 0.1,
                              cy + dy + math.sin(a) * 0.1, 0.012, gold))
    return out
