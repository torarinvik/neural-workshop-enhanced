# -*- coding: utf-8 -*-
"""Paint :mod:`neural_workshop.space` polygons onto a RungTask's batch.

A batch does not keep the order shapes were made in, so every polygon
gets a group of its own, numbered in drawing order; each is drawn as a
dark rim with its fill set a pixel or two inside it, which is what
gives the solids their edges.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Callable, Optional, Sequence, Tuple

import pyglet

RIM = (34, 36, 42)

Place = Callable[[float, float], Tuple[float, float]]


def begin(task) -> None:
    """Start numbering layers afresh for a redraw."""
    task.space_layer = 0


def layer(task):
    """The next group in drawing order, above the task's cards."""
    task.space_layer = getattr(task, 'space_layer', 0) + 1
    return pyglet.graphics.Group(order=task.space_layer,
                                 parent=task.body_group)


def polygon(task, points: Sequence[Tuple[float, float]], colour,
            rim: Optional[Tuple[int, int, int]] = RIM,
            rim_px: float = 1.6, group=None) -> None:
    """One polygon in page coordinates, rimmed or not."""
    if len(points) < 3:
        return
    group = group or layer(task)
    flat = [c for p in points for c in p]
    if rim is not None:
        task.drawn.append(pyglet.shapes.Polygon(
            *points, color=rim, batch=task.batch, group=group))
        cx = sum(x for x, _y in points) / len(points)
        cy = sum(y for _x, y in points) / len(points)
        inner = []
        for x, y in points:
            d = math.hypot(x - cx, y - cy)
            k = max(0.0, (d - rim_px) / d) if d > 0 else 0.0
            inner.append((cx + (x - cx) * k, cy + (y - cy) * k))
        points = inner
        group = pyglet.graphics.Group(order=1, parent=group)
    del flat
    task.drawn.append(pyglet.shapes.Polygon(
        *points, color=colour, batch=task.batch, group=group))


def paint(task, painted, place: Place, rim_px: float = 1.6) -> None:
    """Painted polygons (farthest first), each point through *place*."""
    for p in painted:
        pts = [place(x, y) for x, y in p.points]
        polygon(task, pts, p.colour, RIM if p.rim else None, rim_px)


def fit(bounds, left, bottom, width, height,
        margin: float = 0.06) -> Place:
    """A placing that fits *bounds* (min x, min y, max x, max y) into a
    box, centred, the same scale both ways."""
    x0, y0, x1, y1 = bounds
    w, h = max(1e-6, x1 - x0), max(1e-6, y1 - y0)
    scale = min(width * (1 - 2 * margin) / w, height * (1 - 2 * margin) / h)
    ox = left + width / 2 - (x0 + x1) / 2 * scale
    oy = bottom + height / 2 - (y0 + y1) / 2 * scale
    return lambda x, y: (ox + x * scale, oy + y * scale)


def scaled(scale: float, cx: float, cy: float) -> Place:
    """A placing at a fixed scale about a page point."""
    return lambda x, y: (cx + x * scale, cy + y * scale)
