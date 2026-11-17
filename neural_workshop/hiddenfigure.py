# -*- coding: utf-8 -*-
"""Hidden Figure: which drawing has the small figure inside it?

A small figure of a few strokes, and some busier drawings. Exactly one
of them contains the figure -- the same strokes, the same way up, the
same size, somewhere among the others. The extra strokes join on to it
and carry the eye across its corners, so it has to be pulled out of the
whole it has become part of.

The ladder:

* rungs 1-3: three strokes, hidden among three more; two drawings;
* rungs 4-6: four strokes among six; three drawings;
* rungs 7-9: among nine; the wrong drawings miss it by one stroke;
* rungs 10-12: five strokes among twelve, on a bigger lattice; four
  drawings;
* from rung 13: more strokes around it every few rungs; six strokes
  and a bigger lattice from rung 16.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import FrozenSet, List, NamedTuple, Optional, Tuple

from . import scenes as S
from .i18n import _

Edge = Tuple[Tuple[int, int], Tuple[int, int]]
Figure = FrozenSet[Edge]
STEPS = ((1, 0), (0, 1), (1, 1), (1, -1))


class Grade(NamedTuple):
    rung: int
    points: int          # the lattice is points x points
    strokes: int
    extra: int
    drawings: int
    near: bool           # wrong drawings miss by one stroke


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        points=4 if r < 10 else 5 if r < 16 else 6,
        strokes=3 if r < 4 else 4 if r < 10 else 5 if r < 16 else 6,
        extra=(3 if r < 4 else 6 if r < 7 else 9 if r < 10 else 12 if r < 13
               else min(30, 14 + (r - 13) // 2)),
        drawings=2 if r < 4 else 3 if r < 10 else 4,
        near=r >= 7)


def lattice(n: int) -> List[Edge]:
    return [((x, y), (x + dx, y + dy)) for x in range(n) for y in range(n)
            for dx, dy in STEPS if 0 <= x + dx < n and 0 <= y + dy < n]


def shift(fig, dx: int, dy: int) -> Figure:
    return frozenset(((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy))
                     for a, b in fig)


def extent(fig) -> Tuple[int, int, int, int]:
    xs = [q[0] for e in fig for q in e]
    ys = [q[1] for e in fig for q in e]
    return min(xs), min(ys), max(xs), max(ys)


def embeds(target: Figure, fig: Figure, n: int) -> bool:
    """Whether *target* (its corner at the origin) lies in *fig* at any
    shift."""
    _x0, _y0, w, h = extent(target)
    return any(shift(target, dx, dy) <= fig
               for dx in range(n - w) for dy in range(n - h))


class Puzzle(NamedTuple):
    level: Grade
    target: Figure
    drawings: List[Figure]
    hue: float
    paper: Tuple[int, int, int]
    question: str
    choices: Tuple[str, ...]
    answer: int


def solve(p: Puzzle) -> Optional[int]:
    hits = [k for k, d in enumerate(p.drawings)
            if embeds(p.target, d, p.level.points)]
    return hits[0] if len(hits) == 1 else None


def _target(k: int, draw: random.Random) -> Figure:
    box = lattice(3)
    fig = {draw.choice(box)}
    while len(fig) < k:
        ends = {q for e in fig for q in e}
        grow = [e for e in box if e not in fig and (e[0] in ends or e[1] in ends)]
        fig.add(draw.choice(grow))
    x0, y0, _x1, _y1 = extent(fig)
    return shift(fig, -x0, -y0)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.points
    every = lattice(n)
    answer = S.slot(seed, level.drawings)
    for _attempt in range(300):
        target = _target(level.strokes, draw)
        _x0, _y0, w, h = extent(target)

        def placed():
            return shift(target, draw.randrange(n - w), draw.randrange(n - h))

        def padded(fig, count):
            fig = set(fig)
            rest = [e for e in every if e not in fig]
            draw.shuffle(rest)
            # Strokes that join on come first: they hide it best.
            ends = {q for e in fig for q in e}
            rest.sort(key=lambda e: not (e[0] in ends or e[1] in ends))
            head = rest[:count * 2]
            draw.shuffle(head)
            return frozenset(fig | set(head[:count]))

        drawings: List[Figure] = []
        ok = True
        for k in range(level.drawings):
            if k == answer:
                drawings.append(padded(placed(), level.extra))
                continue
            for _try in range(60):
                if level.near:
                    base = set(placed())
                    base.discard(draw.choice(sorted(base)))
                    fig = padded(base, level.extra + 1)
                else:
                    fig = frozenset(draw.sample(every,
                                                level.strokes + level.extra))
                if not embeds(target, fig, n) and fig not in drawings:
                    drawings.append(fig)
                    break
            else:
                ok = False
                break
        if not ok:
            continue
        p = Puzzle(level, target, drawings, draw.random(),
                   draw.choice(S.PAPERS),
                   _('Which drawing has the small figure inside it?'),
                   tuple(str(k + 1) for k in range(level.drawings)), answer)
        if solve(p) == answer:
            return p
    raise RuntimeError('no drawings for rung %d' % rung)


def scene(p: Puzzle, t: float = 0.0, judged: bool = False) -> list:
    n = p.level.points
    count = len(p.drawings)
    w = S.W / count
    c = min((w - 0.1) / (n - 1), 0.46 / (n - 1))
    ink = S.hsv(p.hue, 0.55, 0.4)
    out = []
    _x0, _y0, tw, th = extent(p.target)
    ox, oy = S.W / 2 - tw * c / 2, 0.8 - th * c / 2
    mark = S.hsv(p.hue + 0.5, 0.75, 0.75) if judged else ink
    for a, b in p.target:
        out.append(S.line(ox + a[0] * c, oy + a[1] * c, ox + b[0] * c,
                          oy + b[1] * c, 0.009, ink))
    for k, fig in enumerate(p.drawings):
        ox = k * w + (w - (n - 1) * c) / 2
        oy = 0.06
        found = None
        if judged:
            for dx in range(n - tw):
                for dy in range(n - th):
                    if shift(p.target, dx, dy) <= fig:
                        found = shift(p.target, dx, dy)
        for e in sorted(fig):
            a, b = e
            out.append(S.line(ox + a[0] * c, oy + a[1] * c, ox + b[0] * c,
                              oy + b[1] * c, 0.009,
                              mark if found and e in found else ink))
        out.append(S.hit(k * w + 0.01, 0.02, w - 0.02, 0.56, k))
        out.append(S.text(k * w + 0.05, 0.54, 0.04, str(k + 1)))
    return out
