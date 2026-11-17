# -*- coding: utf-8 -*-
"""Drawing glyphs: a glyph, in its look, into a box on the page.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet

from .. import shapekit as G
from . import polish


def ink(lk: G.Look):
    return polish.darker(lk.colours[0], 0.6)


def panel(task, lk: G.Look, x, y, w, h, border=None, thick=2.0,
          paper=None) -> None:
    """A rounded card in the look's paper colour."""
    polish.card(task.drawn, task.batch, x, y, w, h, paper or lk.paper,
                radius=min(w, h) * 0.08,
                edge=border or (196, 196, 204), group=task.card_group)
    if border is not None and thick > 2:
        task.drawn.append(pyglet.shapes.Box(
            x - thick / 2, y - thick / 2, w + thick, h + thick,
            thickness=thick, color=border, batch=task.batch,
            group=task.body_group))


def shape(task, lk: G.Look, name: str, colour, cx, cy, r, turn, fill,
          group=None) -> None:
    """One copy of a shape, centred at (cx, cy), reaching *r*."""
    group = group or pyglet.graphics.Group(order=6, parent=task.body_group)
    pts = [(cx + px * r, cy + py * r) for px, py in G.outline(name, turn)]
    rim = polish.darker(colour, 0.35)
    width = max(1.5, r * 0.14)
    if fill == 0:
        task.drawn.append(pyglet.shapes.Polygon(*pts, color=colour,
                                                batch=task.batch, group=group))
    if fill == 2:
        inner = [(cx + px * r * 0.5, cy + py * r * 0.5)
                 for px, py in G.outline(name, turn)]
        task.drawn.append(pyglet.shapes.Polygon(*inner, color=colour,
                                                batch=task.batch, group=group))
    top = pyglet.graphics.Group(order=7, parent=task.body_group)
    edge = colour if fill else rim
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        task.drawn.append(pyglet.shapes.Line(a[0], a[1], b[0], b[1],
                                             thickness=width if fill else 1.5,
                                             color=edge, batch=task.batch,
                                             group=top))
        if fill:
            task.drawn.append(pyglet.shapes.Circle(a[0], a[1], width / 2,
                                                   color=edge,
                                                   batch=task.batch,
                                                   group=top))


def glyph(task, lk: G.Look, g: G.Glyph, x, y, w, h,
          colour: Optional[tuple] = None) -> None:
    """*g* drawn into the box at (x, y), w by h."""
    half = min(w, h) / 2
    ox, oy = G.cell_at(g.cell)
    cx0, cy0 = x + w / 2 + ox * half, y + h / 2 + oy * half
    scale = half * (0.5 if g.cell >= 0 else 1.0)
    spots = G.spots(g.count)
    each = G.radius(g.size) * scale
    turn = G.seen_turn(lk, g) * math.pi / 4 + 0.0
    name = lk.shapes[g.shape]
    for sx, sy in spots:
        shape(task, lk, name, colour or lk.colours[g.colour],
              cx0 + sx * scale * 0.95, cy0 + sy * scale * 0.95, each, turn,
              g.fill)
