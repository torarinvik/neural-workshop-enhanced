# -*- coding: utf-8 -*-
"""Crossings on screen: two coloured lines on a squared notebook page.

A red line and a blue one, each with a round cap at either end, and from
rung 10 green decoys in the same weight. After the verdict, every place
red crosses blue is ringed.

For the agent boundary: ports 0-6 answer 0-6 crossings.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import crossings as model
from ..i18n import _
from . import polish
from .spacetask import ChoiceTask

RED = (226, 58, 70)
BLUE = (40, 110, 230)
GREEN = (40, 168, 90)


class Crossings(ChoiceTask):
    """How many times does red cross blue?"""

    instance: Optional['Crossings'] = None

    TITLE = 'Crossings'
    TASK_ID = 'crossings'
    PREFIX = 'CROSSINGS'
    CATEGORY = 'attention'
    FOOTNOTE = _('0-6 or click: how many crossings   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._0 <= symbol <= key._9:
            self.choose(symbol - key._0)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        d, batch = self.drawn, self.batch
        s = min(width / model.W, height / model.H)
        w, h = model.W * s, model.H * s
        x0, y0 = left + (width - w) / 2, bottom + (height - h) / 2
        polish.card(d, batch, x0, y0, w, h, (252, 252, 246), radius=12,
                    edge=(200, 206, 220), group=self.card_group)
        step = 5 * s
        k = 1
        while k * step < w:
            d.append(pyglet.shapes.Line(x0 + k * step, y0 + 2,
                                        x0 + k * step, y0 + h - 2,
                                        thickness=1,
                                        color=(190, 210, 236, 120),
                                        batch=batch, group=self.body_group))
            k += 1
        k = 1
        while k * step < h:
            d.append(pyglet.shapes.Line(x0 + 2, y0 + k * step,
                                        x0 + w - 2, y0 + k * step,
                                        thickness=1,
                                        color=(190, 210, 236, 120),
                                        batch=batch, group=self.body_group))
            k += 1
        thick = max(3.0, s * 0.7)
        lines = [(g, GREEN) for g in p.decoys] + [(p.blue, BLUE),
                                                  (p.red, RED)]
        for order, (line, colour) in enumerate(lines):
            g = pyglet.graphics.Group(order=3 + order)
            pts = [(x0 + a * s, y0 + b * s) for a, b in line]
            for a, b in zip(pts, pts[1:]):
                d.append(pyglet.shapes.Line(a[0], a[1], b[0], b[1],
                                            thickness=thick, color=colour,
                                            batch=batch, group=g))
                d.append(pyglet.shapes.Circle(b[0], b[1], thick / 2,
                                              color=colour, batch=batch,
                                              group=g))
            for end in (pts[0], pts[-1]):
                d.append(pyglet.shapes.Circle(end[0], end[1], thick * 1.2,
                                              color=colour, batch=batch,
                                              group=g))
        if self.phase == 'judged':
            for cx, cy in p.crossings:
                d.append(pyglet.shapes.Arc(x0 + cx * s, y0 + cy * s,
                                           thick * 3, thickness=3,
                                           color=(250, 180, 30), batch=batch,
                                           group=pyglet.graphics.Group(
                                               order=12)))
