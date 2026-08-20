# -*- coding: utf-8 -*-
"""Points, outlines and the one transform every shape is drawn through.

Everything here works in **cell-local coordinates**: the origin is the
top-left of a cell and y grows *downward*, which is the space the
original Java generator drew in. Screen space is y-up, so the flip
happens once, in the renderer, rather than being spread through the
rules where it would be easy to get half-right.

A shape is a closed outline — a tuple of points, first point not
repeated at the end. Ellipses are flattened to outlines too, so that
one code path fills, strokes and compares every shape.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, NamedTuple, Sequence, Tuple


class Point(NamedTuple):
    """A position in cell-local coordinates."""

    x: float
    y: float


#: Outline of a shape: the corners, in order, without repeating the first.
Outline = Tuple[Point, ...]

#: Segments an ellipse is flattened into. Cells are drawn at several
#: hundred pixels and then supersampled, so the flattening has to stay
#: below the eye's resolution at that size: at 72 segments the chord of
#: a full-cell circle sits under a third of a pixel from the true arc.
ELLIPSE_SEGMENTS = 72


def ellipse_outline(width: float, height: float,
                    segments: int = ELLIPSE_SEGMENTS) -> Outline:
    """An ellipse of this size, centred on the origin."""
    half_width = width / 2.0
    half_height = height / 2.0
    step = 2.0 * math.pi / segments
    return tuple(Point(half_width * math.cos(index * step),
                       half_height * math.sin(index * step))
                 for index in range(segments))


def transformed(outline: Sequence[Point], scale: float, rotation: int,
                position: Point) -> Outline:
    """Place an origin-centred outline into the cell.

    Scale first, then rotate, then translate — the order the Java
    renderer composed its :class:`AffineTransform` in, and not an
    interchangeable one: rotating before scaling would shear every
    shape whose width and height differ.

    The rotation is clockwise on screen, because y grows downward
    here; the sign matches what the original drew.
    """
    radians = math.radians(rotation)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    placed = []
    for point in outline:
        x = point.x * scale
        y = point.y * scale
        placed.append(Point(x * cosine - y * sine + position.x,
                            x * sine + y * cosine + position.y))
    return tuple(placed)


def bounds(outline: Sequence[Point]) -> Tuple[float, float, float, float]:
    """``(min_x, min_y, max_x, max_y)`` of an outline."""
    xs = [point.x for point in outline]
    ys = [point.y for point in outline]
    return min(xs), min(ys), max(xs), max(ys)


def signed_area(outline: Sequence[Point]) -> float:
    """Twice the signed area; negative when the winding is reversed."""
    total = 0.0
    count = len(outline)
    for index in range(count):
        current = outline[index]
        following = outline[(index + 1) % count]
        total += current.x * following.y - following.x * current.y
    return total


def _inside(point: Point, first: Point, second: Point, third: Point) -> bool:
    """Is ``point`` within the triangle, edges included?"""
    def side(a: Point, b: Point) -> float:
        return ((b.x - a.x) * (point.y - a.y)
                - (b.y - a.y) * (point.x - a.x))

    one, two, three = side(first, second), side(second, third), \
        side(third, first)
    return not ((one < 0 or two < 0 or three < 0)
                and (one > 0 or two > 0 or three > 0))


def is_convex(outline: Sequence[Point]) -> bool:
    """Does the outline turn the same way at every corner?"""
    corners = list(outline)
    if len(corners) < 3:
        return False
    seen_positive = seen_negative = False
    for index in range(len(corners)):
        previous, current, following = (corners[index - 1], corners[index],
                                        corners[(index + 1) % len(corners)])
        cross = ((current.x - previous.x) * (following.y - current.y)
                 - (current.y - previous.y) * (following.x - current.x))
        if cross > 0:
            seen_positive = True
        elif cross < 0:
            seen_negative = True
        if seen_positive and seen_negative:
            return False
    return True


def triangulate(outline: Sequence[Point]) -> List[Tuple[Point, Point, Point]]:
    """Cut an outline into triangles.

    A convex outline is fanned from its first corner, which is exact
    and costs one triangle per corner. Anything else is ear clipped.

    The distinction is not an optimisation detail: a fan over the tee —
    the one concave shape, and what :class:`pyglet.shapes.Polygon`
    would do to it — paints straight across the notch between the arms.
    Ear clipping is correct for both, but its check that nothing else
    lies inside a candidate ear compares every corner against every
    other, and a flattened ellipse has seventy-odd corners. Sending the
    convex shapes the short way took the cost of drawing a puzzle from
    five dropped frames to none.
    """
    corners = list(outline)
    if len(corners) < 3:
        return []
    if signed_area(corners) < 0:
        corners.reverse()
    if is_convex(corners):
        return [(corners[0], corners[index], corners[index + 1])
                for index in range(1, len(corners) - 1)]

    triangles: List[Tuple[Point, Point, Point]] = []
    guard = 0
    while len(corners) > 3 and guard <= len(corners):
        for index in range(len(corners)):
            previous = corners[index - 1]
            current = corners[index]
            following = corners[(index + 1) % len(corners)]

            cross = ((current.x - previous.x) * (following.y - current.y)
                     - (current.y - previous.y) * (following.x - current.x))
            if cross <= 0:
                continue        # reflex corner, not an ear
            if any(_inside(other, previous, current, following)
                   for position, other in enumerate(corners)
                   if other not in (previous, current, following)
                   and position != index):
                continue        # something else is in the way
            triangles.append((previous, current, following))
            del corners[index]
            guard = 0
            break
        else:
            break               # no ear found; outline is degenerate
        guard += 1
    if len(corners) == 3:
        triangles.append((corners[0], corners[1], corners[2]))
    return triangles
