# -*- coding: utf-8 -*-
"""Drawing polyominoes as solid shapes: squares filled, inner seams
hidden, the outline drawn round the whole.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import polyomino as P
from . import polish


def shape(task, s: P.Shape, x, y, cell, fill, edge=None, group=None,
          hole: bool = False) -> None:
    """*s* with its top-left at (x, y + its height), *cell* a square."""
    h, _w = P.size_of(s)
    group = group or task.body_group
    top = pyglet.graphics.Group(order=group.order + 1, parent=group.parent) \
        if hasattr(group, 'order') else group
    edge = edge or polish.darker(fill, 0.4)
    for r, c in s:
        task.drawn.append(pyglet.shapes.Rectangle(
            x + c * cell, y + (h - 1 - r) * cell, cell + 0.6, cell + 0.6,
            color=fill, batch=task.batch, group=group))
    thick = max(1.5, cell * (0.06 if not hole else 0.1))
    for (x0, y0), (x1, y1) in P.outline(s):
        task.drawn.append(pyglet.shapes.Line(
            x + x0 * cell, y + (h - y0) * cell, x + x1 * cell,
            y + (h - y1) * cell, thickness=thick, color=edge,
            batch=task.batch, group=top))


def fit(s: P.Shape, w, h, margin=0.1) -> float:
    """The cell size that fits *s* into w by h."""
    sh, sw = P.size_of(s)
    return min(w * (1 - 2 * margin) / sw, h * (1 - 2 * margin) / sh)
