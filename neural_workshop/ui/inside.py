# -*- coding: utf-8 -*-
"""Inside or Out? on screen: a line drawn in ink on a sheet of paper.

The closed line is drawn as one even stroke of ink with rounded corners,
loose decoy lines in the very same ink, and the dot (or two) as a bright
bead. Nothing is shaded: the inside of the line looks exactly like the
outside, as it must. After the verdict, the inside is washed in colour.

For the agent boundary: port 0 answers Inside (Yes), port 1 Outside (No).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import inside as model
from ..i18n import _
from . import polish
from .spacetask import ChoiceTask

PAPER = (250, 244, 228)
INK = (40, 46, 70)
DOT = (236, 72, 80)


class InsideOrOut(ChoiceTask):
    """Is the dot inside the closed line?"""

    instance: Optional['InsideOrOut'] = None

    TITLE = 'Inside or Out?'
    TASK_ID = 'inside_or_out'
    PREFIX = 'INSIDE'
    CATEGORY = 'perception'
    FOOTNOTE = _('I: inside / yes   O: outside / no   or click   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in (key.I, key.Y):
            self.choose(0)
        elif symbol in (key.O, key.N):
            self.choose(1)
        else:
            super()._key(symbol, modifiers)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        d, batch = self.drawn, self.batch
        n = p.size + 2
        cell = min(width / n, height / n)
        side = cell * n
        x0 = left + (width - side) / 2
        y0 = bottom + (height - side) / 2
        polish.card(d, batch, x0 - 8, y0 - 8, side + 16, side + 16, PAPER,
                    radius=14, edge=(214, 200, 170), group=self.card_group)

        def at(pt):
            return x0 + (pt[0] + 1) * cell, y0 + (pt[1] + 1) * cell
        g = pyglet.graphics.Group(order=3)
        if self.phase == 'judged':
            wash = (120, 200, 160, 110)
            for cx, cy in p.region:
                sx, sy = at((cx, cy))
                d.append(pyglet.shapes.Rectangle(sx, sy, cell, cell,
                                                 color=wash, batch=batch,
                                                 group=self.body_group))
        thick = max(2.0, min(5.0, cell * 0.28))
        for line, closed in [(lp, True) for lp in p.loops] + \
                [(dl, False) for dl in p.decoys]:
            pts = [at(q) for q in line]
            pairs = list(zip(pts, pts[1:] + pts[:1])) if closed else \
                list(zip(pts, pts[1:]))
            for a, b in pairs:
                d.append(pyglet.shapes.Line(a[0], a[1], b[0], b[1],
                                            thickness=thick, color=INK,
                                            batch=batch, group=g))
            for q in pts:
                d.append(pyglet.shapes.Circle(q[0], q[1], thick / 2,
                                              color=INK, batch=batch,
                                              group=g))
        r = max(4.0, cell * 0.3)
        for k, dot in enumerate(p.dots):
            sx, sy = at(dot)
            colour = DOT if k == 0 else (60, 140, 240)
            polish.glow(d, batch, sx, sy, r * 2.4, colour, strength=90,
                        group=self.text_group)
            d.append(pyglet.shapes.Circle(sx, sy, r, color=colour,
                                          batch=batch, group=self.top_group))
            d.append(pyglet.shapes.Circle(sx - r * 0.3, sy + r * 0.3,
                                          r * 0.3, color=(255, 255, 255),
                                          batch=batch, group=self.top_group))
