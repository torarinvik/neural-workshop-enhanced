# -*- coding: utf-8 -*-
"""Touching? on screen: bright shapes on a soft card.

Each shape in its own colour, outlined (thickly, higher up) or filled.
After the verdict, every touching point is ringed in gold.

For the agent boundary: ports 0-2 answer Apart, Touching, Overlapping;
when pairs are counted, ports 0-5 answer 0-5.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import touching as model
from ..i18n import _
from . import polish
from .spacetask import ChoiceTask

HUES = ((236, 84, 96), (52, 130, 236), (250, 176, 40), (60, 186, 120),
        (156, 92, 220), (240, 120, 60))


class Touching(ChoiceTask):
    """Apart, touching, or overlapping?"""

    instance: Optional['Touching'] = None

    TITLE = 'Touching?'
    TASK_ID = 'touching'
    PREFIX = 'TOUCHING'
    CATEGORY = 'perception'
    FOOTNOTE = _('A: apart   T: touching   O: overlapping   (or the '
                 'number keys, or click)   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _key(self, symbol: int, modifiers: int) -> None:
        if self.puzzle is not None and len(self.puzzle.choices) == 3:
            pick = {key.A: 0, key.T: 1, key.O: 2}.get(symbol)
            if pick is not None:
                self.choose(pick)
                return
        if key._0 <= symbol <= key._9 and len(self.puzzle.choices) > 3:
            self.choose(symbol - key._0)
            return
        super()._key(symbol, modifiers)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        d, batch = self.drawn, self.batch
        s = min(width / model.WORLD, height / (model.WORLD * 0.62))
        w, h = model.WORLD * s, model.WORLD * 0.62 * s
        x0, y0 = left + (width - w) / 2, bottom + (height - h) / 2
        polish.card(d, batch, x0, y0, w, h, (246, 244, 252), radius=16,
                    edge=(210, 206, 230), group=self.card_group)
        thick = max(2.5, s * (0.9 if p.level.thick else 0.45))
        for k, sh in enumerate(p.shapes):
            colour = HUES[k % len(HUES)]
            g = pyglet.graphics.Group(order=3 + k % 2)
            cx, cy = x0 + sh.x * s, y0 + sh.y * s
            if sh.kind == 'circle':
                if sh.filled:
                    d.append(pyglet.shapes.Circle(cx, cy, sh.r * s,
                                                  color=colour + (150,),
                                                  segments=96, batch=batch,
                                                  group=g))
                d.append(pyglet.shapes.Arc(cx, cy, sh.r * s, segments=128,
                                           thickness=thick, color=colour,
                                           batch=batch, group=g))
            else:
                pts = [(x0 + a * s, y0 + b * s)
                       for a, b in model._square_pts(sh)]
                if sh.filled:
                    d.append(pyglet.shapes.Polygon(*pts,
                                                   color=colour + (150,),
                                                   batch=batch, group=g))
                for i in range(4):
                    a, b = pts[i], pts[(i + 1) % 4]
                    d.append(pyglet.shapes.Line(a[0], a[1], b[0], b[1],
                                                thickness=thick, color=colour,
                                                batch=batch, group=g))
                    d.append(pyglet.shapes.Circle(a[0], a[1], thick / 2,
                                                  color=colour, batch=batch,
                                                  group=g))
        if self.phase == 'judged':
            for i in range(len(p.shapes)):
                for j in range(i):
                    a, b = p.shapes[i], p.shapes[j]
                    if abs(model.gap(a, b)) < 1e-3:
                        ang = math.atan2(b.y - a.y, b.x - a.x)
                        px = x0 + (a.x + math.cos(ang) * a.r) * s \
                            if a.kind == 'circle' else x0 + (a.x + b.x) / 2 * s
                        py = y0 + (a.y + math.sin(ang) * a.r) * s \
                            if a.kind == 'circle' else y0 + (a.y + b.y) / 2 * s
                        d.append(pyglet.shapes.Arc(
                            px, py, thick * 3, thickness=3,
                            color=(240, 190, 40), batch=batch,
                            group=self.top_group))
