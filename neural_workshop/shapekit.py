# -*- coding: utf-8 -*-
"""Shape kit: small figures made of a handful of properties, in many looks.

A glyph is a shape drawn in a colour, at a size, some number of times,
turned, filled one of three ways and set somewhere in its panel. The
reasoning tasks built on these -- Analogies, Odd One Out, Which Side?,
Triples, Card Sort, Same or Different? and others -- ask about the
*relations* between such properties, and a relation learned on one
look should carry to the next. So every deal draws its own **look**:
which shapes stand for shape 0, 1, 2..., which colours for colour 0,
1, 2..., the paper, the ink. A task asks about indices; the look turns
them into pictures, and no two deals need look alike.

Everything here is pure: no pyglet. :mod:`neural_workshop.ui.glyphpaint`
draws a glyph into a box.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Sequence, Tuple

#: Every shape a look may pick from. The ones in ORIENTED look different
#: when turned by 45 degrees, so turning means something for them.
SHAPES = ('circle', 'square', 'triangle', 'diamond', 'pentagon',
          'hexagon', 'star', 'cross', 'arrow', 'heart', 'moon', 'tee',
          'ell', 'kite', 'drop', 'bolt')
ORIENTED = ('triangle', 'arrow', 'heart', 'moon', 'tee', 'ell', 'kite',
            'drop', 'bolt')

#: Colour families: each a set of hues far enough apart to name.
PALETTES = (
    ((222, 64, 64), (40, 120, 220), (250, 180, 30), (50, 170, 90),
     (150, 80, 200), (240, 120, 40)),
    ((200, 40, 120), (20, 160, 170), (240, 200, 40), (90, 60, 160),
     (110, 170, 40), (230, 90, 80)),
    ((30, 90, 160), (230, 80, 40), (60, 160, 120), (200, 160, 30),
     (170, 60, 140), (90, 90, 90)),
    ((180, 40, 40), (40, 140, 60), (40, 60, 180), (220, 140, 20),
     (120, 40, 140), (20, 150, 200)),
)
PAPERS = ((250, 248, 242), (240, 246, 252), (252, 244, 236),
          (244, 250, 240), (248, 244, 252))

SIZES = 3            # small, middle, large
COUNTS = 4           # one to four copies
TURNS = 8            # eighths of a turn
FILLS = 3            # solid, outline, half (an outline round a smaller solid)
CELLS = 9            # where in a 3 x 3 panel; -1 for the middle, unasked

ATTRS = ('shape', 'colour', 'size', 'count', 'turn', 'fill', 'cell')


class Glyph(NamedTuple):
    shape: int           # index into the look's shapes
    colour: int          # index into the look's colours
    size: int = 1
    count: int = 1
    turn: int = 0
    fill: int = 0
    cell: int = -1


class Look(NamedTuple):
    shapes: Tuple[str, ...]
    colours: Tuple[Tuple[int, int, int], ...]
    paper: Tuple[int, int, int]
    tilt: float          # a small turn of the whole panel's layout


def look(draw: random.Random, shapes: int = 6, colours: int = 4,
         oriented: bool = False) -> Look:
    """A fresh look: *shapes* shapes (all of them oriented, if asked)
    and *colours* colours, in a random order."""
    pool = list(ORIENTED if oriented else SHAPES)
    draw.shuffle(pool)
    pal = list(draw.choice(PALETTES))
    draw.shuffle(pal)
    return Look(tuple(pool[:shapes]), tuple(pal[:colours]),
                draw.choice(PAPERS), draw.uniform(-0.15, 0.15))


def oriented(lk: Look, g: Glyph) -> bool:
    return lk.shapes[g.shape] in ORIENTED


# --- outlines ----------------------------------------------------------------

def _regular(n: int, phase: float = math.pi / 2, r: float = 1.0):
    return [(r * math.cos(phase + 2 * math.pi * k / n),
             r * math.sin(phase + 2 * math.pi * k / n)) for k in range(n)]


def _outline(name: str) -> List[Tuple[float, float]]:
    """The shape's outline, about the origin, reaching about 1."""
    if name == 'circle':
        return _regular(40)
    if name == 'square':
        return _regular(4, math.pi / 4, 1.2)
    if name == 'triangle':
        return _regular(3, math.pi / 2, 1.15)
    if name == 'diamond':
        return [(0, 1.1), (-0.72, 0), (0, -1.1), (0.72, 0)]
    if name == 'pentagon':
        return _regular(5)
    if name == 'hexagon':
        return _regular(6, 0.0)
    if name == 'star':
        return [p for k in range(5) for p in (
            (math.cos(math.pi / 2 + 2 * math.pi * k / 5),
             math.sin(math.pi / 2 + 2 * math.pi * k / 5)),
            (0.42 * math.cos(math.pi / 2 + 2 * math.pi * (k + 0.5) / 5),
             0.42 * math.sin(math.pi / 2 + 2 * math.pi * (k + 0.5) / 5)))]
    if name == 'cross':
        a, b = 0.33, 0.95
        return [(a, b), (-a, b), (-a, a), (-b, a), (-b, -a), (-a, -a),
                (-a, -b), (a, -b), (a, -a), (b, -a), (b, a), (a, a)]
    if name == 'arrow':
        return [(0, 1), (-0.75, 0.15), (-0.3, 0.15), (-0.3, -1),
                (0.3, -1), (0.3, 0.15), (0.75, 0.15)]
    if name == 'heart':
        pts = []
        for k in range(40):
            t = 2 * math.pi * k / 40
            x = 16 * math.sin(t) ** 3
            y = (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t)
                 - math.cos(4 * t))
            pts.append((x / 17.0, y / 17.0 + 0.1))
        return pts
    if name == 'moon':
        # A crescent: the unit circle from 60 to 300 degrees round the
        # left, and back along a circle centred to the right.
        cx = 0.6
        r = math.hypot(0.5 - cx, math.sin(math.pi / 3))
        top = math.atan2(math.sin(math.pi / 3), 0.5 - cx)
        outer = [(math.cos(t), math.sin(t)) for t in
                 [math.pi / 3 + (4 * math.pi / 3) * k / 24 for k in range(25)]]
        inner = [(cx + r * math.cos(t), r * math.sin(t)) for t in
                 [2 * math.pi - top - (2 * math.pi - 2 * top) * k / 16
                  for k in range(1, 16)]]
        return outer + inner
    if name == 'tee':
        return [(-1, 1), (1, 1), (1, 0.45), (0.3, 0.45), (0.3, -1),
                (-0.3, -1), (-0.3, 0.45), (-1, 0.45)]
    if name == 'ell':
        return [(-0.7, 1), (-0.1, 1), (-0.1, -0.4), (0.8, -0.4),
                (0.8, -1), (-0.7, -1)]
    if name == 'kite':
        return [(0, 1.1), (-0.6, 0.35), (0, -1.0), (0.6, 0.35)]
    if name == 'drop':
        pts = [(0, 1.1)]
        for k in range(1, 30):
            t = math.pi * (0.15 + 1.7 * k / 30.0) + math.pi / 2
            pts.append((0.62 * math.cos(t), -0.35 + 0.62 * math.sin(t)))
        return pts
    if name == 'bolt':
        return [(0.2, 1), (-0.6, -0.1), (-0.05, -0.1), (-0.3, -1),
                (0.6, 0.15), (0.05, 0.15), (0.35, 1)]
    raise ValueError(name)


_CACHE = {}


def outline(name: str, turn: float = 0.0) -> List[Tuple[float, float]]:
    """The outline of *name* turned by *turn* radians, counterclockwise."""
    if name not in _CACHE:
        _CACHE[name] = _outline(name)
    c, s = math.cos(turn), math.sin(turn)
    return [(x * c - y * s, x * s + y * c) for x, y in _CACHE[name]]


def radius(size: int) -> float:
    """One copy's reach, as a share of its panel's half width -- the
    same however many copies there are, so a size means one thing."""
    return (0.2, 0.3, 0.42)[max(0, min(2, size))]


def spots(count: int) -> List[Tuple[float, float]]:
    """Where the copies of a glyph sit, as shares of the panel."""
    return {1: [(0, 0)], 2: [(-0.5, 0), (0.5, 0)],
            3: [(-0.5, -0.4), (0.5, -0.4), (0, 0.45)],
            4: [(-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5)]
            }[max(1, min(4, count))]


def cell_at(cell: int) -> Tuple[float, float]:
    """The middle of 3 x 3 cell *cell*, as shares of the panel (-1..1)."""
    if cell < 0:
        return 0.0, 0.0
    return ((cell % 3) - 1) * 0.62, (1 - cell // 3) * 0.62


def domain(attr: str) -> int:
    return {'size': SIZES, 'count': COUNTS, 'turn': TURNS, 'fill': FILLS,
            'cell': CELLS}.get(attr, 0)


def random_glyph(draw: random.Random, lk: Look, **fixed) -> Glyph:
    g = Glyph(draw.randrange(len(lk.shapes)), draw.randrange(len(lk.colours)),
              draw.randrange(SIZES), 1, 0, draw.randrange(FILLS), -1)
    if oriented(lk, g):
        g = g._replace(turn=draw.randrange(TURNS))
    return g._replace(**fixed)


def differ(a: Glyph, b: Glyph) -> List[str]:
    return [n for n in ATTRS if getattr(a, n) != getattr(b, n)]


def seen_turn(lk: Look, g: Glyph) -> int:
    """The turn as it shows: a shape with no orientation shows none."""
    if not oriented(lk, g):
        return 0
    return g.turn % TURNS


def seen(lk: Look, g: Glyph) -> Tuple:
    """What can be seen of *g* -- two glyphs that look the same give the
    same tuple."""
    return (lk.shapes[g.shape], g.colour, g.size, g.count, seen_turn(lk, g),
            g.fill, g.cell)


def all_seen_distinct(lk: Look, gs: Sequence[Glyph]) -> bool:
    return len({seen(lk, g) for g in gs}) == len(gs)
