# -*- coding: utf-8 -*-
"""Behind the Screen: things go behind it, some come out; how many now?

A screen stands on a stage. Balls roll in and go behind it; some roll
on out the other side, some come back, some enter from the wings
straight behind. When it is over: how many are behind the screen now?

Nothing behind the screen can be seen, so the count has to be kept
from the comings and goings -- the oldest test of knowing that a thing
still exists when it is out of sight, with arithmetic on top.

The ladder:

* rungs 1-3: one to three balls roll in behind and stay;
* rungs 4-6: three or four, and some roll on out the far side;
* rungs 7-9: two colours, and the question is about one;
* rungs 10-12: two screens, and balls cross from one to the other;
* from rung 13: a ball more every two rungs, to fourteen, faster, and
  more of them on the move at once.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

HUES = ((230, 80, 70), (60, 120, 230), (250, 180, 40), (60, 170, 100))


class Grade(NamedTuple):
    rung: int
    balls: Tuple[int, int]
    leave: bool
    colours: int
    screens: int
    speed: float         # stage widths a second
    overlap: float       # 0: one at a time; 1: all at once


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        balls=((1, 3) if r < 4 else (3, 4) if r < 7 else (4, 5) if r < 13
               else (5, min(14, 5 + (r - 13) // 2))),
        leave=r >= 4,
        colours=1 if r < 7 else 2,
        screens=1 if r < 10 else 2,
        speed=0.35 if r < 7 else 0.45 if r < 13 else min(0.9, 0.5 + 0.02 * (r - 13)),
        overlap=0.0 if r < 7 else 0.3 if r < 13 else min(0.9, 0.4 + 0.04 * (r - 13)))


class Ball(NamedTuple):
    colour: int
    lane: float                          # height on the stage, 0..1
    path: Tuple[Tuple[float, float], ...]   # (time, x), x off-stage < 0 or > 1


class Puzzle(NamedTuple):
    level: Grade
    screens: List[Tuple[float, float]]
    balls: List[Ball]
    asked_screen: int
    asked_colour: int    # -1: any colour
    hues: Tuple[Tuple[int, int, int], ...]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def where(b: Ball, t: float) -> float:
    path = b.path
    if t <= path[0][0]:
        return path[0][1]
    for (t0, x0), (t1, x1) in zip(path, path[1:]):
        if t0 <= t <= t1:
            return x0 + (x1 - x0) * (t - t0) / max(1e-9, t1 - t0)
    return path[-1][1]


def behind(p: Puzzle, s: int, t: float) -> List[int]:
    a, b = p.screens[s]
    return [k for k, ball in enumerate(p.balls)
            if a + 0.01 < where(ball, t) < b - 0.01]


def solve(p: Puzzle) -> int:
    t = p.open_at
    return sum(1 for k in behind(p, p.asked_screen, t)
               if p.asked_colour < 0 or p.balls[k].colour == p.asked_colour)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    screens = [(0.38, 0.62)] if level.screens == 1 else \
        [(0.16, 0.38), (0.62, 0.84)]
    most = 3 if level.rung < 4 else 5 if level.rung < 13 else 8
    # The count wanted, chosen first so that no one answer is a safe bet.
    want = draw.randint(1 if level.rung < 4 else 0,
                        min(most, level.balls[1] if level.rung >= 4 else 3))
    for _attempt in range(4000):
        if _attempt and _attempt % 400 == 0:
            want = max(0, want - 1)
        n = draw.randint(*level.balls)
        balls = []
        t = 0.6
        for k in range(n):
            colour = draw.randrange(level.colours)
            lane = 0.15 + 0.7 * (k + draw.uniform(0.2, 0.8)) / n
            s = draw.randrange(level.screens)
            a, b = screens[s]
            spot = draw.uniform(a + 0.04, b - 0.04)
            from_left = draw.random() < 0.5
            start = -0.06 if from_left else 1.06
            far = 1.06 if from_left else -0.06
            run = abs(spot - start) / level.speed
            path = [(t, start), (t + run, spot)]
            t_end = t + run
            fate = draw.random()
            if level.leave and fate < 0.35:
                # On out the far side.
                path.append((t_end + draw.uniform(0.3, 0.9), spot))
                path.append((path[-1][0] + abs(far - spot) / level.speed, far))
            elif level.screens == 2 and fate < 0.6:
                # Across to the other screen.
                a2, b2 = screens[1 - s]
                spot2 = draw.uniform(a2 + 0.04, b2 - 0.04)
                path.append((t_end + draw.uniform(0.3, 0.9), spot))
                path.append((path[-1][0] + abs(spot2 - spot) / level.speed,
                             spot2))
            elif level.leave and fate < 0.7:
                # Back out the way it came.
                path.append((t_end + draw.uniform(0.3, 0.9), spot))
                path.append((path[-1][0] + abs(start - spot) / level.speed,
                             start))
            balls.append(Ball(colour, lane, tuple(path)))
            step = run * (1 - level.overlap) + 0.25
            t += step
        end = max(b.path[-1][0] for b in balls) + 0.5
        asked_screen = draw.randrange(level.screens)
        asked_colour = draw.randrange(level.colours) if level.colours > 1 \
            else -1
        hues = tuple(draw.sample(HUES, 2))
        p = Puzzle(level, screens, balls, asked_screen, asked_colour, hues,
                   end, end + 8.0, (), (), '', tuple(str(k) for k in
                                                     range(most + 1)), 0)
        answer = solve(p)
        if answer != want:
            continue
        if level.rung < 4 and answer == 0:
            continue
        if level.screens == 2:
            q = _('How many are behind the left screen?') if asked_screen \
                == 0 else _('How many are behind the right screen?')
        else:
            q = _('How many are behind the screen?')
        if asked_colour >= 0:
            q = q.replace(_('How many'), _('How many of this colour'))
        return p._replace(question=q, answer=answer)
    raise RuntimeError('no stage for rung %d' % rung)
