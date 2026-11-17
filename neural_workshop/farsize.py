# -*- coding: utf-8 -*-
"""Far Size: which post is really the tallest?

Posts standing on flat ground that runs away to the horizon. A far post
is drawn small and a near one large; which is the tallest post really?
The ground tells: a post's foot is as far below the horizon as the eye
is above the ground there, so a post whose top just reaches the horizon
is exactly as tall as the eye is high, wherever it stands.

The ladder:

* rungs 1-3: two posts, one half as tall again, and it looks it;
* rungs 4-6: the taller post is the farther, and drawn the smaller;
* rungs 7-9: posts of different thickness; a quarter taller;
* rungs 10-12: three posts; an eighth;
* from rung 13: four posts from rung 16; the difference closing
  toward one part in forty; no lines on the ground from rung 19.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

HORIZON = 0.62
EYE = 0.55           # how far below the horizon the ground lies at depth 1


class Grade(NamedTuple):
    rung: int
    posts: int
    ratio: float
    against: bool        # the tallest is drawn smaller than another
    widths: bool
    lines: bool          # lines on the ground


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        posts=2 if r < 10 else 3 if r < 16 else 4,
        ratio=(1.5 if r < 4 else 1.4 if r < 7 else 1.25 if r < 10
               else 1.125 if r < 13 else max(1.025, 1.1 - 0.005 * (r - 13))),
        against=r >= 4,
        widths=r >= 7,
        lines=r < 19)


class Post(NamedTuple):
    x: float             # on the page
    depth: float         # 1 the nearest
    height: float        # in eye-heights
    width: float         # likewise


class Puzzle(NamedTuple):
    level: Grade
    posts: List[Post]
    vanish: float
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def foot(post: Post) -> float:
    return HORIZON - EYE / post.depth


def tall(post: Post) -> float:
    """How tall the post is drawn."""
    return post.height * EYE / post.depth


def solve(p: Puzzle) -> int:
    # Its drawn height against how far its foot is below the horizon.
    real = [tall(q) / (HORIZON - foot(q)) for q in p.posts]
    return real.index(max(real))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.posts
    answer = S.slot(seed, n)
    for _attempt in range(500):
        low = draw.uniform(0.45, 0.85)
        heights = [low * draw.uniform(0.97, 1.0) for _k in range(n)]
        heights[answer] = low * level.ratio
        depths = [draw.uniform(1.15, 3.6) for _k in range(n)]
        posts = [Post((k + 0.5) * S.W / n + draw.uniform(-0.1, 0.1) * 2 / n,
                      depths[k], heights[k],
                      draw.uniform(0.07, 0.16) if level.widths else 0.1)
                 for k in range(n)]
        drawn = [tall(q) for q in posts]
        biggest = drawn.index(max(drawn))
        if level.against != (biggest != answer):
            continue
        if level.against and drawn[answer] > 0.8 * max(drawn):
            continue
        if max(foot(q) + tall(q) for q in posts) > 0.97:
            continue
        if min(abs(a - b) for i, a in enumerate(depths)
               for b in depths[i + 1:]) < 0.35:
            continue
        names = (_('Left'), _('Right')) if n == 2 else \
            tuple(str(k + 1) for k in range(n))
        return Puzzle(level, posts, draw.uniform(0.6, 1.0), draw.random(),
                      draw.choice(S.PAPERS),
                      _('Which post is really the tallest?'), names, answer)
    raise RuntimeError('no posts for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    out = [S.rect(0.0, HORIZON, S.W, 1.0 - HORIZON, S.hsv(0.58, 0.25, 0.95)),
           S.rect(0.0, 0.0, S.W, HORIZON, S.hsv(p.hue, 0.25, 0.75))]
    line = S.hsv(p.hue, 0.3, 0.55)
    if p.level.lines:
        for k in range(-12, 13):
            # Each runs from the vanishing point to the page's edge.
            x, y = p.vanish + k * 0.5, 0.0
            if x < 0 or x > S.W:
                edge = 0.0 if x < 0 else S.W
                y = HORIZON * (1 - (edge - p.vanish) / (x - p.vanish))
                x = edge
            out.append(S.line(p.vanish, HORIZON, x, y, 0.003, line))
        for d in (1.0, 1.25, 1.6, 2.1, 2.8, 3.8, 5.5, 9.0):
            y = HORIZON - EYE / d
            out.append(S.line(0.0, y, S.W, y, 0.003, line))
    out.append(S.line(0.0, HORIZON, S.W, HORIZON, 0.004, line))
    n = len(p.posts)
    for k in sorted(range(n), key=lambda k: -p.posts[k].depth):
        q = p.posts[k]
        w = q.width * EYE / q.depth
        out.append(S.rect(q.x - w / 2, foot(q), w, tall(q),
                          S.hsv(p.hue + 0.45, 0.6, 0.55)))
        out.append(S.rect(q.x - w / 2, foot(q), w * 0.3, tall(q),
                          S.hsv(p.hue + 0.45, 0.6, 0.42)))
        if n > 2:
            out.append(S.text(q.x, foot(q) - 0.035, 0.04, str(k + 1)))
        if judged:
            out.append(S.text(q.x, foot(q) + tall(q) + 0.03, 0.035,
                              '%.2f' % q.height))
    for k in range(n):
        out.append(S.hit(k * S.W / n + 0.005, 0.005, S.W / n - 0.01, 0.99, k))
    return out
