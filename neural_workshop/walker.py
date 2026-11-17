# -*- coding: utf-8 -*-
"""Walker: which way is the figure walking?

Eleven lights on the joints of someone walking on the spot: head,
shoulder, hip, elbows, wrists, knees, ankles. Still, they are a scatter
of dots; moving, they are a person, and it can be seen which way the
person faces -- knees lead and elbows trail. Higher up the lights are
lost among others that move as joints move, but are scattered about
and belong to nobody.

The ladder:

* rungs 1-3: the limbs are drawn in;
* rungs 4-6: lights only;
* rungs 7-9: eight stray lights; the walker smaller, anywhere;
* rungs 10-12: sixteen;
* from rung 13: more every rung, to sixty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

LEFT, RIGHT = 0, 1
PERIOD = 1.2
#: Pairs of joints with a limb between them.
BONES = ((0, 1), (1, 2), (2, 3), (3, 4), (1, 5), (5, 6), (2, 7), (7, 8),
         (1, 9), (9, 10))


class Grade(NamedTuple):
    rung: int
    limbs: bool
    strays: int
    size: float          # the walker's height on the page


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        limbs=r < 4,
        strays=(0 if r < 7 else 8 if r < 10 else 16 if r < 13
                else min(60, 24 + 3 * (r - 13))),
        size=0.78 if r < 7 else 0.5)


def joints(phase: float, facing: int) -> List[Tuple[float, float]]:
    """The eleven joints of a walker one unit tall, feet near nought,
    facing right (+1) or left (-1): head, shoulder, hip, then knee,
    ankle, elbow, wrist of the near side and of the far."""
    bob = 0.012 * math.cos(2 * phase)
    hip = (0.0, 0.53 + bob)
    sh = (0.015, 0.82 + bob)
    head = (0.03, 0.95 + bob)
    out = [head, sh, hip]
    for side in (0.0, math.pi):
        ph = phase + side
        thigh = 0.45 * math.sin(ph)
        # The knee bends as the leg swings through, and only backward.
        flex = 0.1 + 0.8 * max(0.0, math.cos(ph + 0.5))
        knee = (hip[0] + 0.26 * math.sin(thigh), hip[1] - 0.26 * math.cos(thigh))
        shin = thigh - flex
        ankle = (knee[0] + 0.26 * math.sin(shin), knee[1] - 0.26 * math.cos(shin))
        out += [knee, ankle]
    for side in (0.0, math.pi):
        ph = phase + side
        upper = -0.4 * math.sin(ph)
        # The elbow bends forward.
        fore = upper + 0.35 + 0.25 * math.sin(ph + math.pi)
        elbow = (sh[0] + 0.17 * math.sin(upper), sh[1] - 0.17 * math.cos(upper))
        wrist = (elbow[0] + 0.16 * math.sin(fore), elbow[1] - 0.16 * math.cos(fore))
        out += [elbow, wrist]
    # Knee, ankle, elbow, wrist for each side in turn.
    order = [0, 1, 2, 3, 4, 7, 8, 5, 6, 9, 10]
    return [(out[k][0] * facing, out[k][1]) for k in order]


class Stray(NamedTuple):
    x: float
    y: float
    joint: int
    facing: int
    phase: float


class Puzzle(NamedTuple):
    level: Grade
    at: Tuple[float, float]      # where the walker's feet are
    facing: int
    phase: float
    strays: Tuple[Stray, ...]
    hue: float
    paper: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def walker(p: Puzzle, t: float) -> List[Tuple[float, float]]:
    ph = p.phase + 2 * math.pi * t / PERIOD
    return [(p.at[0] + x * p.level.size, p.at[1] + y * p.level.size)
            for x, y in joints(ph, p.facing)]


MIDDLES = [tuple(sum(joints(2 * math.pi * k / 16, 1)[j][axis] for k in range(16))
                 / 16.0 for axis in (0, 1)) for j in range(11)]


def strays(p: Puzzle, t: float) -> List[Tuple[float, float]]:
    out = []
    for s in p.strays:
        ph = s.phase + 2 * math.pi * t / PERIOD
        x, y = joints(ph, s.facing)[s.joint]
        mx, my = MIDDLES[s.joint]
        out.append((s.x + (x - mx * s.facing) * p.level.size,
                    s.y + (y - my) * p.level.size))
    return out


def solve(p: Puzzle) -> int:
    # Knees lead: over a stride the knee lies ahead of the line from
    # hip to ankle.
    lead = 0.0
    for k in range(24):
        j = walker(p, PERIOD * k / 24.0)
        for knee, ankle in ((3, 4), (7, 8)):
            lead += j[knee][0] - (j[2][0] + j[ankle][0]) / 2
    return RIGHT if lead > 0 else LEFT


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, 2)
    size = level.size
    if level.strays:
        at = (draw.uniform(0.3, S.W - 0.3), draw.uniform(0.05, 0.95 - size))
    else:
        at = (S.W / 2 + draw.uniform(-0.3, 0.3), 0.08)
    lost = []
    for k in range(level.strays):
        # As many facing each way, so the strays lean neither.
        lost.append(Stray(draw.uniform(0.08, S.W - 0.08), draw.uniform(0.08, 0.92),
                          draw.randrange(11), 1 if k % 2 else -1,
                          draw.uniform(0, 2 * math.pi)))
    return Puzzle(level, at, 1 if answer == RIGHT else -1,
                  draw.uniform(0, 2 * math.pi), tuple(lost), draw.random(),
                  (26, 28, 36), 0.8, 10.0, (), (),
                  _('Which way is the figure facing?'),
                  (_('Left'), _('Right')), answer)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    ink = S.hsv(p.hue, 0.15, 0.95)
    j = walker(p, t)
    if p.level.limbs or judged:
        limb = (215, 60, 60) if judged and not p.level.limbs else (110, 115, 135)
        for a, b in BONES:
            out.append(S.line(j[a][0], j[a][1], j[b][0], j[b][1], 0.006, limb))
    for x, y in j + strays(p, t):
        out.append(S.disc(x, y, 0.011, ink))
    return out
