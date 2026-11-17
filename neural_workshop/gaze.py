# -*- coding: utf-8 -*-
"""Gaze: what is the face looking at?

A face, and numbered things around it. Each eye's pupil sits toward
what the face is looking at -- each eye for itself, so the two do not
point quite the same way: they converge on the thing. Which thing is
it? Low down the things lie well apart; higher up they crowd together,
and some lie one behind another on the same line from the face, where
only how far the eyes converge tells them apart.

The ladder:

* rungs 1-3: three things, a sixth of a turn apart or more;
* rungs 4-6: four, forty degrees apart;
* rungs 7-9: five, twenty-five degrees;
* rungs 10-12: six, and one lies behind or before the thing looked
  at, on the same line;
* from rung 13: eight things, closing toward six degrees apart.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

HEAD = 0.19
EYE_OUT = 0.085      # each eye from the middle of the face
EYE_R = 0.05
PUPIL_R = 0.021
REACH = EYE_R - PUPIL_R - 0.004


class Grade(NamedTuple):
    rung: int
    things: int
    apart: float         # degrees between bearings from the face, at least
    inline: bool         # a thing on the same line as the one looked at


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        things=3 if r < 4 else 4 if r < 7 else 5 if r < 10 else 6 if r < 13 else 8,
        apart=(60.0 if r < 4 else 40.0 if r < 7 else 25.0 if r < 10
               else 20.0 if r < 13 else max(6.0, 18.0 * 0.92 ** (r - 13))),
        inline=r >= 10)


class Puzzle(NamedTuple):
    level: Grade
    face: Tuple[float, float]
    things: List[Tuple[float, float]]
    pupils: List[Tuple[float, float]]    # each pupil's centre
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def eyes(face) -> List[Tuple[float, float]]:
    return [(face[0] - EYE_OUT, face[1] + 0.03),
            (face[0] + EYE_OUT, face[1] + 0.03)]


def looking(face, thing) -> List[Tuple[float, float]]:
    """Where the two pupils sit when the face looks at *thing*."""
    out = []
    for ex, ey in eyes(face):
        a = math.atan2(thing[1] - ey, thing[0] - ex)
        out.append((ex + math.cos(a) * REACH, ey + math.sin(a) * REACH))
    return out


def solve(p: Puzzle) -> int:
    def miss(thing):
        total = 0.0
        for (ex, ey), (px, py) in zip(eyes(p.face), p.pupils):
            a = math.atan2(py - ey, px - ex)
            b = math.atan2(thing[1] - ey, thing[0] - ex)
            total += abs((a - b + math.pi) % (2 * math.pi) - math.pi)
        return total
    scores = [miss(th) for th in p.things]
    return scores.index(min(scores))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.things
    answer = S.slot(seed, n)

    def on_page(q):
        return 0.06 < q[0] < S.W - 0.06 and 0.06 < q[1] < 0.94

    for _attempt in range(2000):
        face = (draw.uniform(0.5, S.W - 0.5), draw.uniform(0.38, 0.62))
        bearings = []
        things = []
        ok = True
        for k in range(n):
            for _try in range(60):
                a = draw.uniform(0, 2 * math.pi)
                d = draw.uniform(0.3, 0.75)
                if level.inline and k == 1:
                    # On the first one's line, half as far or twice.
                    a = bearings[0]
                    d0 = math.hypot(things[0][0] - face[0], things[0][1] - face[1])
                    d = d0 * draw.choice((0.5, 2.0))
                    if d < 0.27:
                        continue
                elif any(abs((a - b + math.pi) % (2 * math.pi) - math.pi)
                         < math.radians(level.apart) for b in bearings):
                    continue
                q = (face[0] + math.cos(a) * d, face[1] + math.sin(a) * d)
                if on_page(q) and all(math.hypot(q[0] - o[0], q[1] - o[1]) > 0.1
                                      for o in things):
                    bearings.append(a)
                    things.append(q)
                    break
            else:
                ok = False
                break
        if not ok:
            continue
        # The inline pair may be the one looked at, or not.
        order = list(range(n))
        draw.shuffle(order)
        things = [things[k] for k in order]
        p = Puzzle(level, face, things, looking(face, things[answer]),
                   draw.random(), draw.choice(S.PAPERS),
                   _('What is the face looking at?'),
                   tuple(str(k + 1) for k in range(n)), answer)
        if solve(p) == answer:
            return p
    raise RuntimeError('no scene for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    fx, fy = p.face
    skin = S.hsv(0.07 + 0.04 * p.hue, 0.35, 0.95)
    out = [S.disc(fx, fy, HEAD, skin),
           S.ring(fx, fy, HEAD, 0.006, S.hsv(0.07, 0.4, 0.5))]
    for (ex, ey), (px, py) in zip(eyes(p.face), p.pupils):
        out.append(S.disc(ex, ey, EYE_R, (255, 255, 255)))
        out.append(S.ring(ex, ey, EYE_R, 0.004, (90, 80, 80)))
        out.append(S.disc(px, py, PUPIL_R, (30, 30, 40)))
        if judged:
            th = p.things[p.answer]
            out.append(S.line(px, py, th[0], th[1], 0.003, (215, 60, 60)))
    out.append(S.line(fx - 0.05, fy - 0.09, fx + 0.05, fy - 0.09, 0.006,
                      (150, 90, 80)))
    for k, (x, y) in enumerate(p.things):
        out.append(S.disc(x, y, 0.035, S.hsv(p.hue + 0.3 + 0.61 * k, 0.5, 0.9)))
        out.append(S.text(x, y, 0.04, str(k + 1)))
        out.append(S.hit(x - 0.045, y - 0.045, 0.09, 0.09, k))
    return out
