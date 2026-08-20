# -*- coding: utf-8 -*-
"""The things drawn in a cell: six shapes and five fills.

A :class:`Surface` is one drawn shape — its kind, its size, and the
scale, rotation, position and fill currently applied to it. Surfaces
are immutable: a rule that rotates a shape returns a new surface
rather than editing one in place. The original Java mutated shared
objects and had to clone them at exactly the right moments to avoid a
change in one cell leaking into another; immutability removes that
class of bug rather than re-implementing the discipline that avoided
it.

Two surfaces compare equal when they would be indistinguishable on
screen. That comparison is load-bearing: it is what stops the answer
choices containing the same picture twice.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Dict, Sequence, Tuple

from .geometry import Outline, Point, ellipse_outline, transformed


@dataclass(frozen=True)
class Fill:
    """A shape's interior: a colour laid over the paper.

    The colours are the originals, and they are translucent — a fill is
    ink washed over white paper, not a flat swatch, so the paper still
    shows through. Keeping the alpha rather than pre-mixing the result
    means the renderer composites exactly what the Java did.
    """

    name: str
    color: Tuple[int, int, int, int]


#: The five fills, lightest to darkest once laid over white paper.
#:
#: The original gave two of these the same name, ``"Red"`` — a
#: copy-paste, since neither is red and both are grey. Because
#: surfaces compared their fills by name, those two counted as the
#: same fill: an answer choice differing from another only in being
#: 46% grey rather than 70% grey was discarded as a duplicate of it,
#: though the two look nothing alike. The names here are distinct, so
#: the comparison sees what the player sees.
WHITE = Fill('white', (255, 255, 255, 0))
GREY_LIGHT = Fill('grey-light', (191, 191, 191, 102))
GREY_MID = Fill('grey-mid', (102, 102, 102, 128))
GREY_DARK = Fill('grey-dark', (26, 26, 26, 153))
BLACK = Fill('black', (0, 0, 0, 191))

#: Every grey, lightest first — the order the cycling rule steps through.
ALL_FILLS: Tuple[Fill, ...] = (WHITE, GREY_LIGHT, GREY_MID, GREY_DARK, BLACK)

#: The three a shape is filled with at random, and the three the
#: constant-fill rule hands out one per route. Three in the original too.
BASIC_FILLS: Tuple[Fill, ...] = (WHITE, BLACK, GREY_LIGHT)

#: Colours, at the opacity of the darkest grey so that a shape behind
#: still shows through by as much as it always did.
COLOUR_ALPHA = 200

YELLOW = Fill('yellow', (240, 228, 66, COLOUR_ALPHA))
SKY = Fill('sky', (86, 180, 233, COLOUR_ALPHA))
VERMILION = Fill('vermilion', (213, 94, 0, COLOUR_ALPHA))
BLUE = Fill('blue', (0, 114, 178, COLOUR_ALPHA))

#: The colours, lightest first.
#:
#: They are four of the Okabe-Ito set, which exists to stay legible to
#: colour-blind eyes, and they were chosen from it by measurement
#: rather than by taste: every pair was simulated for each kind of
#: dichromacy and compared in CIELAB, and this is the four that leave
#: the largest worst case. That worst case is a little over twice the
#: grey ramp's own, so a rule about colour is no harder to follow than
#: a rule about shading, and for some eyes it is easier.
#:
#: The order is by lightness, and strictly: 100, 91, 76, 63, 57. That
#: is deliberate. It means the sequence is a lightness ramp as well as
#: a colour one, so a player who cannot separate the hues at all can
#: still follow the rule by how dark each step is — the same rule they
#: would be following in the grey puzzles.
COLOUR_FILLS: Tuple[Fill, ...] = (WHITE, YELLOW, SKY, VERMILION, BLUE)

#: The three most widely separated of them.
BASIC_COLOURS: Tuple[Fill, ...] = (WHITE, YELLOW, BLUE)


@dataclass(frozen=True)
class Palette:
    """A set of fills, and what to call the thing they vary.

    A puzzle picks one and keeps it. Mixing greys and colours inside a
    single puzzle would make a wrong answer identifiable by its palette
    rather than by the rules, which is not the question being asked.
    """

    name: str
    #: All five, in cycle order, for the rule that steps along them.
    ramp: Tuple[Fill, ...]
    #: The three used for a shape's own fill and for the constant-fill
    #: rule, which hands one to each route.
    basic: Tuple[Fill, ...]
    #: What a rule about these is called when a puzzle is explained.
    noun: str


GREYS = Palette('greys', ALL_FILLS, BASIC_FILLS, 'shading')
COLOURS = Palette('colours', COLOUR_FILLS, BASIC_COLOURS, 'colour')

#: Both, for a run that wants colour in the mix.
PALETTES: Tuple[Palette, ...] = (GREYS, COLOURS)

#: The shapes, by name. Only the outline differs between them, so they
#: are a table of outline builders rather than six near-identical
#: classes.
ELLIPSE = 'ellipse'
RECTANGLE = 'rectangle'
TRIANGLE = 'triangle'
TEE = 'tee'
DIAMOND = 'diamond'
TRAPEZOID = 'trapezoid'

#: The six shapes a surface can be, in the original's order.
SHAPE_KINDS: Tuple[str, ...] = (ELLIPSE, RECTANGLE, TRIANGLE, TEE,
                                DIAMOND, TRAPEZOID)


def _rectangle(width: float, height: float) -> Outline:
    half_width, half_height = width / 2.0, height / 2.0
    return (Point(-half_width, -half_height), Point(half_width, -half_height),
            Point(half_width, half_height), Point(-half_width, half_height))


def _triangle(width: float, height: float) -> Outline:
    half_width, half_height = width / 2.0, height / 2.0
    return (Point(-half_width, half_height), Point(half_width, half_height),
            Point(0.0, -half_height))


def _diamond(width: float, height: float) -> Outline:
    half_width, half_height = width / 2.0, height / 2.0
    quarter_height = half_height / 2.0
    return (Point(-half_width, -quarter_height), Point(0.0, half_height),
            Point(half_width, -quarter_height), Point(0.0, -half_height))


def _trapezoid(width: float, height: float) -> Outline:
    half_width, half_height = width / 2.0, height / 2.0
    quarter_width = half_width / 2.0
    return (Point(-half_width, half_height), Point(half_width, half_height),
            Point(quarter_width, -half_height),
            Point(-quarter_width, -half_height))


def _tee(width: float, height: float) -> Outline:
    """The one concave shape, which is why the renderer ear-clips."""
    half_width, quarter_width = width / 2.0, width / 4.0
    half_height, quarter_height = height / 2.0, height / 4.0
    return (Point(-half_width, -half_height), Point(half_width, -half_height),
            Point(half_width, -quarter_height),
            Point(quarter_width, -quarter_height),
            Point(quarter_width, half_height),
            Point(-quarter_width, half_height),
            Point(-quarter_width, -quarter_height),
            Point(-half_width, -quarter_height))


#: Shape name → the builder for its origin-centred outline.
_OUTLINES = {
    ELLIPSE: lambda width, height: ellipse_outline(width, height),
    RECTANGLE: _rectangle,
    TRIANGLE: _triangle,
    TEE: _tee,
    DIAMOND: _diamond,
    TRAPEZOID: _trapezoid,
}


@dataclass(frozen=True)
class Surface:
    """One shape drawn in a cell.

    ``width`` and ``height`` are the shape's own size; ``scale`` is
    applied on top of them when drawing, and the two are kept apart
    because the rules change them separately — a scaling rule multiplies
    ``scale`` and leaves the shape's identity alone.
    """

    kind: str
    width: float
    height: float
    position: Point
    fill: Fill
    scale: float = 1.0
    rotation: int = 0

    def outline(self) -> Outline:
        """The shape as it should be drawn, in cell-local coordinates."""
        return transformed(_OUTLINES[self.kind](self.width, self.height),
                           self.scale, self.rotation, self.position)

    # --- the rules' edits, each returning a new surface ------------------

    def scaled(self, factor: float) -> 'Surface':
        return replace(self, scale=factor)

    def rotated(self, degrees: int) -> 'Surface':
        return replace(self, rotation=degrees % 360)

    def filled(self, fill: Fill) -> 'Surface':
        return replace(self, fill=fill)

    def moved(self, position: Point) -> 'Surface':
        return replace(self, position=position)

    def looks_like(self, other: 'Surface') -> bool:
        """Would these two be indistinguishable on screen?

        Drawn size is ``width * scale``, so a half-size shape at double
        scale is the same picture as the shape itself and must not be
        offered as a second answer choice. Comparing the fields raw
        would miss that.

        Rotation is compared outright rather than modulo half a turn.
        Half a turn does leave a rectangle or an ellipse looking
        identical, but it does not leave a triangle, a tee or a
        trapezoid alone, and treating those as duplicates would throw
        away sound answer choices.
        """
        return (self.kind == other.kind
                and self.fill.name == other.fill.name
                and self.rotation == other.rotation
                and _close(self.position.x, other.position.x)
                and _close(self.position.y, other.position.y)
                and _close(self.width * self.scale,
                           other.width * other.scale)
                and _close(self.height * self.scale,
                           other.height * other.scale))


def _close(one: float, two: float) -> bool:
    """Equal to within a fraction of a pixel at any drawing size."""
    return abs(one - two) < 1e-6


def generate_surface(cell_size: int, rng: random.Random,
                     fills: Sequence[Fill] = BASIC_FILLS) -> Surface:
    """A random shape, centred in a cell of ``cell_size``.

    The sizes come in quarter-cell steps, and the two dimensions are
    tied: a shape two quarters wide is three tall and vice versa, so
    the generator never produces a square-ish blob that reads as the
    same picture whichever way it is rotated.
    """
    half = cell_size / 2.0
    quarter = half / 2.0

    width = rng.randrange(3) * quarter + quarter
    if width == 2 * quarter:
        height = 3 * quarter
    elif width == 3 * quarter:
        height = 2 * quarter
    else:
        height = rng.randrange(2) * quarter + half
    if rng.random() < 0.5:
        width, height = height, width

    return Surface(kind=rng.choice(SHAPE_KINDS), width=width, height=height,
                   position=Point(half, half),
                   fill=rng.choice(list(fills)))


def same_picture(one: Sequence[Surface], two: Sequence[Surface]) -> bool:
    """Do two collections of surfaces draw the same cell?

    Order does not matter — the surfaces in a cell are painted on top
    of one another — so this is a matching, not a zip.
    """
    if len(one) != len(two):
        return False
    unmatched = list(two)
    for surface in one:
        for index, candidate in enumerate(unmatched):
            if surface.looks_like(candidate):
                del unmatched[index]
                break
        else:
            return False
    return True


#: Shape name → how it is described in the explanation of a puzzle.
SHAPE_NAMES: Dict[str, str] = {
    ELLIPSE: 'ellipse', RECTANGLE: 'rectangle', TRIANGLE: 'triangle',
    TEE: 'tee', DIAMOND: 'diamond', TRAPEZOID: 'trapezoid',
}
