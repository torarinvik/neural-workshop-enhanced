# -*- coding: utf-8 -*-
"""Arrow Walk.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import carried as model
from .. import framed
from .carried import POINTS, CarriedTask


class ArrowWalk(CarriedTask):
    """Arrow Walk."""

    instance = None
    TITLE = 'Arrow Walk'
    TASK_ID = 'arrow_walk'
    PREFIX = 'ARROWWALK'
    KIND = 'arrows'
    LOOK = 0

    def _arrow(self, direction: str, cx, cy, size, colour) -> None:
        dx, dy = POINTS[direction]
        thick = size * 0.12
        tail = (cx - dx * size * 0.45, cy - dy * size * 0.45)
        neck = (cx + dx * size * 0.1, cy + dy * size * 0.1)
        self.drawn.append(pyglet.shapes.Line(
            *tail, *neck, thickness=thick, color=colour,
            batch=self.batch, group=self.text_group))
        tip = (cx + dx * size * 0.5, cy + dy * size * 0.5)
        px, py = -dy, dx
        self.drawn.append(pyglet.shapes.Triangle(
            *tip, neck[0] + px * size * 0.25, neck[1] + py * size * 0.25,
            neck[0] - px * size * 0.25, neck[1] - py * size * 0.25,
            color=colour, batch=self.batch, group=self.text_group))

    def _draw_arrows(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        look, data = p.data['look'], p.data
        f, showing = self._frame(t)
        side = min(height * 0.9, width * 0.42)
        cell = side / 2
        pane = side * 0.7
        bx, by = self._placed(left + width * 0.08, bottom, width * 0.5,
                              height, side, side)
        ax = left + width * 0.78
        ay = bottom + height / 2
        order = framed.port_order(look, model.CARDS)
        for port in range(model.CARDS):
            square = order[port]
            row, col = divmod(square, 2)
            x = bx + col * cell
            y = by + (1 - row) * cell
            self._card(port, x + cell * 0.05, y + cell * 0.05, cell * 0.9,
                       cell * 0.9)
            if showing is not None and f == 0 and square == data['start']:
                self.drawn.append(pyglet.shapes.Circle(
                    x + cell / 2, y + cell / 2, cell * 0.25,
                    color=self._colour(), batch=self.batch,
                    group=self.text_group))
        if showing is not None and f > 0:
            self._arrow(model.ARROWS[data['arrows'][f - 1]], ax, ay, pane,
                        self._colour())
        self._asked(left + width * 0.04, bottom + height * 0.85,
                    cell * 0.25)
