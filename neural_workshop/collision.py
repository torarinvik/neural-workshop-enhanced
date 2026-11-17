# -*- coding: utf-8 -*-
"""Collision Course: will the two balls hit?

Two balls roll steadily across the page toward where their ways cross,
and before they get there they are covered. Will they hit each other?
One may pass in front of the other, or behind: the answer is in their
ways and their speeds together.

The ladder:

* rungs 1-3: their ways are drawn; they hit square on or miss by
  four ball-widths;
* rungs 4-6: no ways drawn;
* rungs 7-9: unlike speeds; a miss by two and a half;
* rungs 10-12: covered sooner; a miss by one and four fifths, a hit
  that may only clip;
* from rung 13: sooner still, the miss closing toward one and a
  fifth.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

YES, NO = 0, 1
R = 0.045


class Grade(NamedTuple):
    rung: int
    ways: bool           # drawn
    speeds: bool         # unlike
    miss: float          # nearest a miss comes, in ball-widths
    clip: float          # farthest off-centre a hit is, in ball-widths
    lead: float          # seconds before they are nearest that they go


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        ways=r < 4,
        speeds=r >= 7,
        miss=(4.0 if r < 7 else 2.5 if r < 10 else 1.8 if r < 13
              else max(1.2, 1.7 - 0.03 * (r - 13))),
        clip=0.1 if r < 10 else 0.6 if r < 13 else 0.8,
        lead=(0.4 if r < 10 else 0.7 if r < 13
              else min(1.3, 0.8 + 0.04 * (r - 13))))


class Ball(NamedTuple):
    x: float
    y: float
    vx: float
    vy: float


class Puzzle(NamedTuple):
    level: Grade
    balls: Tuple[Ball, Ball]
    cut: float                   # when they are covered
    hues: Tuple[float, float]
    paper: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def at(b: Ball, t: float) -> Tuple[float, float]:
    return b.x + b.vx * t, b.y + b.vy * t


def nearest(p: Puzzle) -> Tuple[float, float]:
    """When the balls are nearest, and how far apart then."""
    a, b = p.balls
    dx, dy = a.x - b.x, a.y - b.y
    vx, vy = a.vx - b.vx, a.vy - b.vy
    t = max(0.0, -(dx * vx + dy * vy) / (vx * vx + vy * vy))
    return t, math.hypot(dx + vx * t, dy + vy * t)


def solve(p: Puzzle) -> int:
    return YES if nearest(p)[1] < 2 * R else NO


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    answer = S.slot(seed, 2)
    for _attempt in range(2000):
        when = draw.uniform(1.8, 2.6)
        cx, cy = draw.uniform(0.6, S.W - 0.6), draw.uniform(0.4, 0.6)
        a1 = draw.uniform(0, 2 * math.pi)
        a2 = a1 + draw.choice((-1, 1)) * math.radians(draw.uniform(50, 130))
        s1 = draw.uniform(0.2, 0.3)
        s2 = s1 * (draw.choice((0.6, 0.75, 1.3, 1.6)) if level.speeds else 1.0)
        v1 = (math.cos(a1) * s1, math.sin(a1) * s1)
        v2 = (math.cos(a2) * s2, math.sin(a2) * s2)
        apart = 2 * R * (draw.uniform(0.0, level.clip) if answer == YES
                         else level.miss * draw.uniform(1.0, 1.25))
        # At their nearest they lie across the way one moves past the other.
        rx, ry = v1[0] - v2[0], v1[1] - v2[1]
        rn = math.hypot(rx, ry)
        nx, ny = -ry / rn, rx / rn
        side = draw.choice((-1, 1))
        p1 = (cx + nx * apart / 2 * side, cy + ny * apart / 2 * side)
        p2 = (cx - nx * apart / 2 * side, cy - ny * apart / 2 * side)
        balls = (Ball(p1[0] - v1[0] * when, p1[1] - v1[1] * when, *v1),
                 Ball(p2[0] - v2[0] * when, p2[1] - v2[1] * when, *v2))
        if not all(R < b.x < S.W - R and R < b.y < 1 - R for b in balls):
            continue
        if math.hypot(balls[0].x - balls[1].x, balls[0].y - balls[1].y) < 0.3:
            continue
        cut = when - level.lead
        p = Puzzle(level, balls, cut, (draw.random(), draw.random()),
                   draw.choice(S.PAPERS), cut, cut + 6.0, (), (),
                   _('Will the two balls hit?'), (_('Yes'), _('No')), answer)
        if solve(p) == answer:
            return p
    raise RuntimeError('no course for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = []
    when, _gap = nearest(p)
    colours = [S.hsv(p.hues[0], 0.6, 0.85), S.hsv(p.hues[0] + 0.45, 0.6, 0.85)]
    if p.level.ways or judged:
        for b in p.balls:
            x0, y0 = at(b, 0.0)
            x1, y1 = at(b, when + 1.0)
            out.append(S.line(x0, y0, x1, y1, 0.003, (170, 170, 180)))
    if judged:
        for b, colour in zip(p.balls, colours):
            x, y = at(b, when)
            out.append(S.disc(x, y, R, colour))
    elif t < p.cut:
        for b, colour in zip(p.balls, colours):
            x, y = at(b, t)
            out.append(S.disc(x, y, R, colour))
    else:
        out.append(S.text(S.W / 2, 0.5, 0.12, '?', (150, 150, 160)))
    return out
