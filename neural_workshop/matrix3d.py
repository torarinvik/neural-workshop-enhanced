# -*- coding: utf-8 -*-
"""3D Matrix: a three-by-three matrix of small constructions.

Each cell holds a construction of solids -- blocks stacked on a table,
a ball or a cone on them, a small cube on top of that, a ramp leaning
on one side, a ring round the foot -- seen from some viewpoint. Each
of its attributes follows one rule over the matrix: the same in every
cell, set by the row, set by the column, each value once in every row
and column, or (for something that is there or not) there in the
third cell of a row when it is in exactly one of the first two. The
ninth cell is missing; pick it from the answers.

The answers are laid out so that none stands out: they are the corners
of a cube over two or three attributes, so every value an answer could
have appears in as many answers as its alternative. Only the matrix
says which is right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

PORTS = 8

#: Each attribute and how many values it has.
DOMAIN = {'ring': 2, 'cap': 2, 'side': 3, 'colour': 3, 'top': 3, 'base': 3,
          'height': 3, 'view': 3}
ATTRS = tuple(DOMAIN)
SAID = {'ring': _('ring'), 'cap': _('small cube'), 'side': _('ramp'),
        'colour': _('colour'), 'top': _('top'), 'base': _('shape'),
        'height': _('blocks'), 'view': _('viewpoint')}
KINDS = {'const': _('the same'), 'row': _('by row'), 'col': _('by column'),
         'latin': _('each once'), 'xor': _('in just one')}

COLOURS = ((0.52, 0.34, 0.74), (0.16, 0.62, 0.60), (0.86, 0.36, 0.26))
RAMP = (0.96, 0.76, 0.20)
RING = (0.27, 0.45, 0.78)
PEARL = (0.93, 0.92, 0.90)
#: Viewpoints: degrees round from the front, degrees above the table.
VIEWS = ((30.0, 30.0), (-30.0, 30.0), (30.0, 62.0))

BLOCK = 0.6          # a block's height
HALF = 0.45          # and half its width
GAP = 0.03


class Build(NamedTuple):
    """One construction, an index into each attribute's values."""
    ring: int = 0        # none, a ring round the foot
    cap: int = 0         # none, a small cube on the very top
    side: int = 0        # the ramp: right, front, left
    colour: int = 0
    top: int = 1         # nothing, a ball, a cone
    base: int = 0        # cube, drum, tub
    height: int = 0      # one, two, three blocks
    view: int = 0


class Part(NamedTuple):
    mesh: str                    # 'box', 'ball', 'drum', 'cone', 'tub',
    #                              'wedge', 'ring'
    pos: Tuple[float, float, float]      # z up, the front towards -y
    mat: Tuple[float, ...]       # a turn, nine numbers by rows
    size: Tuple[float, float, float]
    colour: Tuple[float, float, float]


class Grade(NamedTuple):
    rung: int
    vary: int                    # attributes that follow a rule
    pool: Tuple[str, ...]        # attributes in play
    kinds: Tuple[str, ...]       # rules in play, besides 'const'
    choices: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    easy = ('ring', 'cap', 'side', 'colour')
    if r < 4:
        return Grade(r, 1, easy, ('row', 'col'), 4)
    if r < 7:
        return Grade(r, 2, easy + ('top',), ('row', 'col'), 4)
    if r < 10:
        return Grade(r, 2, easy + ('top', 'base'), ('row', 'col', 'latin'),
                     6)
    if r < 13:
        return Grade(r, 3, easy + ('top', 'base', 'height'),
                     ('row', 'col', 'latin', 'xor'), 6)
    if r < 16:
        return Grade(r, 3, ATTRS, ('row', 'col', 'latin', 'xor'), 6)
    return Grade(r, 4 if r < 19 else 5 if r < 25 else 6, ATTRS,
                 ('row', 'col', 'latin', 'xor'), 8)


class Puzzle(NamedTuple):
    level: Grade
    cells: Tuple[Build, ...]     # nine, by rows; the last is the missing one
    options: Tuple[Build, ...]
    choices: Tuple[str, ...]
    answer: int
    rules: Tuple[Tuple[str, str], ...]   # (attribute, kind) of each rule
    seed: int
    question: str


# --- the rules -----------------------------------------------------------

def _rule(draw: random.Random, attr: str, kind: str):
    n = DOMAIN[attr]
    if kind == 'const':
        return ('const', draw.randrange(n))
    if kind in ('row', 'col'):
        if n >= 3:
            values = draw.sample(range(n), 3)
        else:
            values = draw.choice([v for v in itertools.product(range(n),
                                                               repeat=3)
                                  if len(set(v)) > 1])
        return (kind, tuple(values))
    if kind == 'latin':
        return ('latin', tuple(draw.sample(range(n), 3)),
                draw.choice((1, -1)))
    if kind == 'xor':
        return ('xor', tuple((draw.randrange(2), draw.randrange(2))
                             for _row in range(3)))
    raise ValueError(kind)


def _value(rule, r: int, c: int) -> int:
    kind = rule[0]
    if kind == 'const':
        return rule[1]
    if kind == 'row':
        return rule[1][r]
    if kind == 'col':
        return rule[1][c]
    if kind == 'latin':
        return rule[1][(r + rule[2] * c) % 3]
    a, b = rule[1][r]
    return (a, b, a ^ b)[c]


def fits(attr: str, kind: str) -> bool:
    n = DOMAIN[attr]
    return {'latin': n >= 3, 'xor': n == 2}.get(kind, True)


def infer(attr: str, seen: List[int]) -> set:
    """Every value the ninth cell could have for *attr*, given the
    eight seen (by rows), under each rule that the eight obey."""
    g = [seen[0:3], seen[3:6], seen[6:8]]
    found = set()
    if all(len(set(row)) == 1 for row in g):
        found.add(g[2][0])                               # by row
    if g[0][0] == g[1][0] == g[2][0] and g[0][1] == g[1][1] == g[2][1] \
            and g[0][2] == g[1][2]:
        found.add(g[0][2])                               # by column
    if DOMAIN[attr] >= 3:
        s = set(g[0])
        cols = [{g[0][c], g[1][c], g[2][c]} for c in (0, 1)]
        if len(s) == 3 and set(g[1]) == s and all(col == s for col in cols) \
                and g[0][2] != g[1][2] and g[2][0] != g[2][1]:
            left = s - set(g[2])
            if left == s - {g[0][2], g[1][2]}:
                found |= left                            # each once
    if DOMAIN[attr] == 2 and all(row[2] == row[0] ^ row[1]
                                 for row in g[:2]):
        found.add(g[2][0] ^ g[2][1])                     # exactly one
    return found


def solve(p: Puzzle) -> Optional[int]:
    """The answer worked out from the eight cells shown: None if they
    leave it open."""
    want = {}
    for attr in ATTRS:
        found = infer(attr, [getattr(cell, attr) for cell in p.cells[:8]])
        if len(found) != 1:
            return None
        want[attr] = found.pop()
    build = Build(**want)
    return p.options.index(build) if build in p.options else None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    default = Build()
    for _attempt in range(2000):
        varying = draw.sample(level.pool, level.vary)
        rules: Dict[str, tuple] = {}
        named = []
        for i, attr in enumerate(varying):
            kinds = [k for k in level.kinds if fits(attr, k)]
            if level.vary >= 2 and i < 2 and 'latin' not in level.kinds:
                kinds = [('row', 'col')[i]]      # one each way
            kind = draw.choice(kinds)
            rules[attr] = _rule(draw, attr, kind)
            named.append((attr, kind))
        for attr in ATTRS:
            if attr not in rules:
                rules[attr] = _rule(draw, attr, 'const') \
                    if attr in level.pool and attr != 'view' \
                    else ('const', getattr(default, attr))
        cells = tuple(Build(**{a: _value(rules[a], r, c) for a in ATTRS})
                      for r in range(3) for c in range(3))
        if len(set(cells[:8])) < 3:
            continue
        # With two rules or more the answer is never a cell already
        # shown: it is to be worked out, not copied. (With one rule it
        # must be one: its own row or column is full of it.)
        if level.vary > 1 and cells[8] in cells[:8]:
            continue
        # The eight shown must settle every attribute of the ninth.
        if any(infer(a, [getattr(cell, a) for cell in cells[:8]])
               != {getattr(cells[8], a)} for a in ATTRS):
            continue
        # A rule that the eight shown do not show at work is no rule.
        if any(len({getattr(cell, a) for cell in cells[:8]}) < 2
               for a in varying):
            continue
        break
    else:
        raise RuntimeError('no matrix for rung %d' % rung)
    # The answers: the corners of a cube over two or three attributes.
    # (Four answers over two rules take every other corner of a cube
    # over the two and something that stands still: answers that only
    # recombine what the two rules show would all be cells on show.)
    axes = 2 if level.choices == 4 and level.vary < 2 else 3
    others = [a for a in level.pool if a not in varying]
    draw.shuffle(varying)
    draw.shuffle(others)
    over = (varying + others)[:axes]
    truth = cells[8]
    swap = {a: draw.choice([v for v in range(DOMAIN[a])
                            if v != getattr(truth, a)]) for a in over}
    corners = list(itertools.product((0, 1), repeat=axes))
    if level.choices == 4 and axes == 3:
        corners = [c for c in corners if sum(c) % 2 == 0]
    if level.choices == 6:
        # Drop two opposite corners, neither the answer: still balanced.
        gone = draw.choice([c for c in corners if 0 < sum(c) < axes])
        corners = [c for c in corners
                   if c != gone and c != tuple(1 - v for v in gone)]
    options = [truth._replace(**{a: swap[a] for a, on in zip(over, corner)
                                 if on}) for corner in corners]
    draw.shuffle(options)
    return Puzzle(level, cells, tuple(options),
                  tuple(str(i + 1) for i in range(len(options))),
                  options.index(truth), tuple(named), seed,
                  _('Which construction completes the matrix?'))


def explain(p: Puzzle) -> str:
    return ';  '.join('%s %s' % (SAID[a], KINDS[k]) for a, k in p.rules)


# --- the solids ----------------------------------------------------------

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _turn(angle: float) -> Tuple[float, ...]:
    c, s = math.cos(angle), math.sin(angle)
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


def tall(b: Build) -> float:
    """How high the construction stands."""
    return (b.height + 1) * BLOCK + (0.0, 0.72, 0.4)[b.top] \
        + (0.26 if b.cap else 0.0)


def parts(b: Build) -> List[Part]:
    """The solids of one construction, standing on z = 0."""
    out: List[Part] = []
    colour = COLOURS[b.colour]
    mesh = ('box', 'drum', 'tub')[b.base]
    n = b.height + 1
    for k in range(n):
        out.append(Part(mesh, (0.0, 0.0, k * BLOCK + BLOCK / 2), IDENTITY,
                        (HALF, HALF, BLOCK / 2 - (GAP / 2 if n > 1 else 0)),
                        colour))
    top = n * BLOCK
    if b.top == 1:
        out.append(Part('ball', (0.0, 0.0, top + 0.36), IDENTITY,
                        (0.36, 0.36, 0.36), PEARL))
        top += 0.72
    elif b.top == 2:
        out.append(Part('cone', (0.0, 0.0, top + 0.3), IDENTITY,
                        (0.36, 0.36, 0.3), PEARL))
        top += 0.6 - 0.2                 # the cube sits down over the tip
    if b.cap:
        out.append(Part('box', (0.0, 0.0, top + 0.13), _turn(0.5),
                        (0.13, 0.13, 0.13), colour))
    angle = (0.0, -math.pi / 2, math.pi)[b.side]
    reach = HALF + 0.275
    out.append(Part('wedge', (reach * math.cos(angle),
                              reach * math.sin(angle), 0.28), _turn(angle),
                    (0.275, 0.3, 0.28), RAMP))
    if b.ring:
        out.append(Part('ring', (0.0, 0.0, 0.1), IDENTITY, (1.42, 1.42, 0.1),
                        RING))
    return out
