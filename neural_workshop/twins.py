# -*- coding: utf-8 -*-
"""Twin tasks: four rules, each dealt in two looks.

A learner that has found a rule in one task should find it sooner in a
task that asks the same thing and looks nothing alike. So each of four
rules -- same or different, the odd one out, what comes next, inside or
outside -- is dealt twice over, as look ``a`` and look ``b``. The two
differ in what is drawn, in its colours, in how it is laid out and in
which port means what; the rule and the ladder are the same, and each
rung adds one thing: one more item to compare, one more item to search,
one more step in the pattern, one more corner on the outline.

Every puzzle has ``choices`` (what each port says) and ``answer``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

SHAPES = ('circle', 'square', 'triangle', 'diamond', 'star', 'cross')
#: Look a draws in these; look b in those. No colour is in both.
HUES_A = ((36, 104, 196), (122, 70, 170), (20, 124, 132), (70, 84, 110))
HUES_B = ((196, 120, 20), (150, 86, 44), (120, 130, 30), (170, 80, 120),
          (90, 100, 110), (60, 130, 150))

RULES = ('same', 'odd', 'next', 'inside')


class Puzzle(NamedTuple):
    rule: str
    look: str                    # 'a' or 'b'
    choices: Tuple[str, ...]     # what each port says
    answer: int
    data: Dict[str, Any]
    question: str


def size(rule: str, rung: int) -> int:
    """How much of its one thing a rung holds."""
    r = max(1, int(rung))
    if rule == 'same':
        return min(r, 12)                    # items in each of the two
    if rule == 'odd':
        return min(r + 2, 12)                # items to search
    if rule == 'next':
        return min(r + 1, 12)                # steps in the pattern
    return min(r + 3, 30)                    # corners, or squares fenced


def deal(rule: str, look: str, rung: int,
         rng: Optional[random.Random] = None) -> Puzzle:
    rng = rng or random.Random()
    return MAKERS[rule](look, size(rule, rung), rng)


def _same(look: str, n: int, rng: random.Random) -> Puzzle:
    kinds = SHAPES if look == 'a' else range(len(HUES_B))
    one = [rng.choice(kinds) for _k in range(n)]
    two = list(one)
    same = rng.random() < 0.5
    if not same:
        at = rng.randrange(n)
        two[at] = rng.choice([k for k in kinds if k != one[at]])
    words = (_('same'), _('different'))
    if look == 'a':
        choices, answer = words, 0 if same else 1
    else:
        choices, answer = words[::-1], 1 if same else 0
    return Puzzle('same', look, choices, answer,
                  {'one': one, 'two': two, 'hue': rng.randrange(4)},
                  _('Are the two the same?'))


def _odd(look: str, n: int, rng: random.Random) -> Puzzle:
    odd = rng.randrange(n)
    if look == 'a':
        base, other = rng.sample(SHAPES, 2)
        data = {'items': [other if k == odd else base for k in range(n)],
                'hue': rng.randrange(4)}
        answer = odd                          # counted from the left
    else:
        base = rng.randrange(4)
        other = rng.choice([k for k in range(4) if k != base])
        data = {'items': [other if k == odd else base for k in range(n)],
                'hue': rng.randrange(len(HUES_B)),
                'turn': rng.random()}
        answer = n - 1 - odd                  # counted back round the ring
    return Puzzle('odd', look, tuple(str(k + 1) for k in range(n)), answer,
                  data, _('Which one is the odd one out?'))


def _whole(seq: List[int]) -> bool:
    """Whether *seq* repeats only at its full length, and has two kinds."""
    p = len(seq)
    if len(set(seq)) < 2:
        return False
    return not any(p % q == 0 and seq == seq[:q] * (p // q)
                   for q in range(1, p))


def _next(look: str, p: int, rng: random.Random) -> Puzzle:
    while True:
        unit = [rng.randrange(3) for _k in range(p)]
        if _whole(unit):
            break
    shown = 2 * p + rng.randrange(p)
    seq = [unit[k % p] for k in range(shown)]
    cards = [0, 1, 2]
    rng.shuffle(cards)                        # cards[port] = what it shows
    if look == 'a':
        kinds = rng.sample(SHAPES, 3)
        hue = rng.randrange(4)
    else:
        kinds = [1, 2, 3]                     # pips on a tile
        hue = rng.randrange(len(HUES_B))
    return Puzzle('next', look, ('1', '2', '3'),
                  cards.index(unit[shown % p]),
                  {'seq': seq, 'cards': cards, 'kinds': kinds, 'hue': hue,
                   'period': p},
                  _('What comes next?'))


def _in_polygon(pts, x: float, y: float) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and \
                x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _off_edge(pts, x: float, y: float) -> float:
    best = 9.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy)
                         / (dx * dx + dy * dy or 1.0)))
        best = min(best, math.hypot(x - x1 - t * dx, y - y1 - t * dy))
    return best


def _inside_a(n: int, rng: random.Random):
    """An outline of *n* corners and a dot clearly in or out of it."""
    while True:
        turn = rng.random() * math.tau
        pts = []
        for k in range(n):
            a = turn + math.tau * (k + rng.uniform(-0.3, 0.3)) / n
            r = rng.uniform(0.4, 1.0)
            pts.append((r * math.cos(a), r * math.sin(a)))
        want = rng.random() < 0.5
        for _try in range(200):
            x, y = rng.uniform(-1, 1), rng.uniform(-1, 1)
            if _in_polygon(pts, x, y) == want and \
                    _off_edge(pts, x, y) >= 0.09:
                return {'points': pts, 'dot': (x, y)}, want


def _inside_b(n: int, rng: random.Random):
    """A fence round *n* squares and a mark in a square in or out."""
    while True:
        cells = {(0, 0)}
        while len(cells) < n:
            x, y = rng.choice(sorted(cells))
            dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            cells.add((x + dx, y + dy))
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
        # The squares outside the fence that the edge of the page
        # reaches, so a hole in the middle is not counted as outside.
        out = {(x0, y0)}
        stack = [(x0, y0)]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = (x + dx, y + dy)
                if x0 <= c[0] <= x1 and y0 <= c[1] <= y1 \
                        and c not in cells and c not in out:
                    out.add(c)
                    stack.append(c)
        if len(out) + len(cells) != (x1 - x0 + 1) * (y1 - y0 + 1):
            continue                          # it has a hole: deal again
        want = rng.random() < 0.5
        near = sorted(c for c in out
                      if any((c[0] + dx, c[1] + dy) in cells
                             for dx, dy in ((1, 0), (-1, 0), (0, 1),
                                            (0, -1))))
        mark = rng.choice(sorted(cells) if want else near)
        return {'cells': cells, 'mark': mark,
                'box': (x0, y0, x1, y1)}, want


def _inside(look: str, n: int, rng: random.Random) -> Puzzle:
    words = (_('inside'), _('outside'))
    if look == 'a':
        data, inside = _inside_a(n, rng)
        data['hue'] = rng.randrange(4)
        choices, answer = words, 0 if inside else 1
    else:
        data, inside = _inside_b(n, rng)
        data['hue'] = rng.randrange(len(HUES_B))
        choices, answer = words[::-1], 1 if inside else 0
    return Puzzle('inside', look, choices, answer, data,
                  _('Is the mark inside or outside?'))


MAKERS = {'same': _same, 'odd': _odd, 'next': _next, 'inside': _inside}
