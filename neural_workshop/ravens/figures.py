# -*- coding: utf-8 -*-
"""The figures drawn in a panel, and the values they can take.

Every figure is a regular polygon — or a circle, which is the limit of
one — inscribed in a circle of a given radius. That is the single
biggest difference from the previous engine, which stretched shapes to
random widths and heights and stacked them on one another. A matrix
made of regular figures at graded sizes reads as a designed thing; one
made of arbitrary ellipses and trapezoids reads as noise, however
sound the rules behind it are.

Each attribute takes values from a short ordered ladder, because the
rules that make a matrix work — step along, hold constant, deal three
out across the rows — are rules about positions on a ladder. An
attribute with no order to it, or with too many values, cannot carry
them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from .geometry import Outline, Point  # noqa: F401  (Point is re-exported)
from .palette import Fill

#: Figure name → how many sides it has, and the angle its first vertex
#: sits at, in degrees clockwise from straight up.
#:
#: The offsets are what make each figure sit the way the eye expects:
#: a triangle on its base, a square square rather than diamond, a
#: pentagon with its point up, a hexagon flat-topped. A regular polygon
#: drawn without one looks tipped over, and a matrix of tipped figures
#: looks like a mistake rather than a puzzle.
POLYGONS: Dict[str, Tuple[int, float]] = {
    'triangle': (3, 0.0),
    'square': (4, 45.0),
    'pentagon': (5, 0.0),
    'hexagon': (6, 30.0),
    'circle': (0, 0.0),
}

#: The figures, in the order they are laid out on the size ladder —
#: fewest sides first, which is also roughly simplest first.
SHAPES: Tuple[str, ...] = ('triangle', 'square', 'pentagon', 'hexagon',
                           'circle')

#: How round a circle is drawn. Panels are rendered several times their
#: final size and scaled down, so this only has to beat the eye at the
#: largest a figure is ever drawn.
CIRCLE_SEGMENTS = 64

#: The smallest and largest share of its slot a figure fills.
SMALLEST, LARGEST = 0.38, 0.95

#: How much of its slot a figure fills, smallest first.
#:
#: A geometric ladder, not an evenly spaced one. What the eye judges is
#: the ratio between two sizes, not the difference: stepping by a fixed
#: amount makes the small end of the ladder obvious and the large end
#: nearly indistinguishable, which is how a rule about size ends up
#: readable in some rows and guesswork in others. Every step here is
#: the same multiple, so every step looks the same size.
def _ladder(smallest: float, largest: float, steps: int) -> Tuple[float, ...]:
    ratio = (largest / smallest) ** (1.0 / (steps - 1))
    return tuple(round(smallest * ratio ** index, 4)
                 for index in range(steps))


SIZES: Tuple[float, ...] = _ladder(SMALLEST, LARGEST, 5)

#: How many turns a rotation rule has to choose between. Three, because
#: that is what distributing three values across a row needs.
TURNS = 3


def turn_ladder(shape: str) -> Tuple[int, ...]:
    """Three turns of ``shape`` that actually look different.

    A regular polygon comes back to itself every ``360 / sides``
    degrees, so the turns worth offering are the ones inside that span.
    A fixed ladder of sixths of a turn does not know this: on a
    triangle it offers 0, 120 and 240, which are three names for the
    same triangle, and the rule is then one the puzzle claims and never
    shows.
    """
    sides = POLYGONS[shape][0]
    if not sides:
        return (0,)             # a circle has no orientation at all
    span = 360.0 / sides
    return tuple(int(round(index * span / TURNS)) for index in range(TURNS))


def polygon(shape: str, radius: float, centre: Point,
            angle: float = 0.0) -> Outline:
    """The outline of one figure, ready to draw."""
    sides, offset = POLYGONS[shape]
    if not sides:
        sides, offset = CIRCLE_SEGMENTS, 0.0
    start = math.radians(offset + angle - 90.0)
    step = 2.0 * math.pi / sides
    return tuple(Point(centre.x + radius * math.cos(start + index * step),
                       centre.y + radius * math.sin(start + index * step))
                 for index in range(sides))


@dataclass(frozen=True)
class Figure:
    """One figure, placed and sized, ready to be drawn.

    ``radius`` is already the drawn radius — the slot's room multiplied
    by the size the rules chose — so nothing downstream has to know
    about layouts.
    """

    shape: str
    centre: Point
    radius: float
    fill: Fill
    angle: int = 0
    #: Which of the layout's components this figure belongs to. Two
    #: components can share a slot centre — the inside-and-outside
    #: layout puts both in the middle — so the centre alone does not
    #: say which is which. Not part of how a figure looks, and so no
    #: part of :meth:`looks_like`.
    component: int = 0

    def outline(self) -> Outline:
        return polygon(self.shape, self.radius, self.centre, self.angle)

    def looks_like(self, other: 'Figure') -> bool:
        """Would these two be indistinguishable on the page?

        A circle has no orientation, and neither has any figure whose
        turn happens to be a whole number of its own symmetries, so
        angles are compared modulo the symmetry rather than outright.
        Treating a hexagon turned by a sixth of a turn as a different
        figure would let two identical panels both be offered.
        """
        if self.shape != other.shape or self.fill.name != other.fill.name:
            return False
        if (abs(self.radius - other.radius) > 1e-6
                or abs(self.centre.x - other.centre.x) > 1e-6
                or abs(self.centre.y - other.centre.y) > 1e-6):
            return False
        return self._turn() == other._turn()

    def _turn(self) -> float:
        sides = POLYGONS[self.shape][0]
        if not sides:
            return 0.0          # a circle looks the same every way up
        return round(self.angle % (360.0 / sides), 6)


#: One panel's worth of figures. Order does not matter — they are drawn
#: on top of one another — so panels are compared as collections.
Panel = Tuple[Figure, ...]


def same_panel(one: Sequence[Figure], two: Sequence[Figure]) -> bool:
    """Do two panels draw the same picture?"""
    if len(one) != len(two):
        return False
    spare = list(two)
    for figure in one:
        for index, candidate in enumerate(spare):
            if figure.looks_like(candidate):
                del spare[index]
                break
        else:
            return False
    return True
