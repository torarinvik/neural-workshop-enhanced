# -*- coding: utf-8 -*-
"""Symmetric? on screen: the pattern, drawn as squares, dots or tiles.

For the agent boundary: port 0 says yes, 1 no.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import symmetry as model
from ..i18n import _
from . import polish
from .spacetask import ChoiceTask


class Symmetry(ChoiceTask):
    """Is it its own mirror image?"""

    instance: Optional['Symmetry'] = None

    TITLE = 'Symmetric?'
    TASK_ID = 'symmetric'
    PREFIX = 'SYMMETRY'
    CATEGORY = 'perception'
    FOOTNOTE = _('Y: yes   N: no   (or 1 / 2, or click)   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _key(self, symbol: int, modifiers: int) -> None:
        pick = {key.Y: 0, key.N: 1}.get(symbol)
        if pick is not None:
            self.choose(pick)
            return
        super()._key(symbol, modifiers)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        g = p.grid
        h, w = len(g), len(g[0])
        pal = model.PALETTES[p.palette]
        cell = min(width * 0.8 / w, height * 0.94 / h)
        x0 = left + (width - cell * w) / 2
        y0 = bottom + (height - cell * h) / 2
        polish.card(self.drawn, self.batch, x0 - cell * 0.4, y0 - cell * 0.4,
                    cell * (w + 0.8), cell * (h + 0.8), pal[0],
                    radius=cell * 0.4, group=self.card_group)
        for i in range(h):
            for j in range(w):
                v = g[i][j]
                if v == 0:
                    continue
                colour = pal[v]
                x, y = x0 + j * cell, y0 + (h - 1 - i) * cell
                if p.style == 'dots':
                    self.drawn.append(pyglet.shapes.Circle(
                        x + cell / 2, y + cell / 2, cell * 0.42,
                        color=colour, batch=self.batch,
                        group=self.body_group))
                elif p.style == 'tiles':
                    polish.rounded(self.drawn, self.batch, x + cell * 0.08,
                                   y + cell * 0.08, cell * 0.84, cell * 0.84,
                                   colour, radius=cell * 0.2,
                                   group=self.body_group)
                else:
                    self.drawn.append(pyglet.shapes.Rectangle(
                        x, y, cell + 0.5, cell + 0.5, color=colour,
                        batch=self.batch, group=self.body_group))
