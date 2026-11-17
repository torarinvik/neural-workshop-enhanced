# -*- coding: utf-8 -*-
"""Spot the Change on screen: the pictures flicker; the parts are
marked faintly and numbered.

For the agent boundary: port k picks part k, in reading order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import spotchange as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint
from .showtask import ShowTask


class SpotChange(ShowTask):
    """One thing changes between the pictures. Where?"""

    instance: Optional['SpotChange'] = None

    TITLE = 'Spot the Change'
    TASK_ID = 'spot_the_change'
    PREFIX = 'SPOT'
    CATEGORY = 'perception'
    BUTTONS = 0
    FOOTNOTE = _('click the part with the change, or press its number   '
                 'Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _key(self, symbol: int, modifiers: int) -> None:
        from pyglet.window import key
        if key._1 <= symbol <= key._9:
            self.choose(symbol - key._1)

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        lk = p.look
        side = min(width, height)
        x0, y0 = left + (width - side) / 2, bottom + (height - side) / 2
        glyphpaint.panel(self, lk, x0, y0, side, side)
        n = p.level.parts
        part = side / n
        for k in range(1, n):
            for a, b, c, d in ((x0 + k * part, y0, x0 + k * part, y0 + side),
                               (x0, y0 + k * part, x0 + side, y0 + k * part)):
                self.drawn.append(pyglet.shapes.Line(
                    a, b, c, d, thickness=1, color=(220, 220, 228),
                    batch=self.batch, group=self.body_group))
        for k in range(n * n):
            col, row = k % n, k // n
            x, y = x0 + col * part, y0 + side - (row + 1) * part
            border, thick = self._mark(k)
            if thick > 2:
                self.drawn.append(pyglet.shapes.Box(
                    x + 2, y + 2, part - 4, part - 4, thickness=thick,
                    color=border, batch=self.batch, group=self.top_group))
            self._text(str(k + 1), x + 6, y + part - 6, calc_fontsize(10),
                       anchor='left', anchor_y='top',
                       colour=(170, 170, 180, 255))
            self.hits.append((x, y, part, part, lambda c=k: self.choose(c)))
        items = p.after if self.phase == 'judged' else model.showing(p, t)
        if items is None:
            return
        cell = side / (max(n, int((p.level.items * 1.6) ** 0.5) + 1)) * 1.5
        for it in items:
            glyphpaint.glyph(self, lk, it.glyph, x0 + it.x * side - cell / 2,
                             y0 + it.y * side - cell / 2, cell, cell)
