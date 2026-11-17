# -*- coding: utf-8 -*-
"""Grid Change on screen: the examples down the left, the new grid and
the candidates on the right.

For the agent boundary: port k picks candidate k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import gridchange as model
from ..geometry import calc_fontsize
from ..i18n import _
from .spacetask import ChoiceTask


class GridChange(ChoiceTask):
    """Do to the new grid what was done to the others."""

    instance: Optional['GridChange'] = None

    TITLE = 'Grid Change'
    TASK_ID = 'grid_change'
    PREFIX = 'GRIDCHANGE'
    CATEGORY = 'reasoning'
    BUTTONS = 0
    FOOTNOTE = _('click the candidate or press its number   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _grid(self, g, x, y, size, border=None, thick=2.0) -> None:
        """*g* drawn into a size-by-size box, cells square."""
        h, w = len(g), len(g[0])
        cell = size / max(h, w)
        ox = x + (size - cell * w) / 2
        oy = y + (size - cell * h) / 2
        self.drawn.append(pyglet.shapes.Rectangle(
            ox - 2, oy - 2, cell * w + 4, cell * h + 4,
            color=border or (90, 90, 100), batch=self.batch,
            group=self.card_group))
        for i, r in enumerate(g):
            for j, v in enumerate(r):
                self.drawn.append(pyglet.shapes.Rectangle(
                    ox + j * cell + 0.5, oy + (h - 1 - i) * cell + 0.5,
                    cell - 1, cell - 1, color=model.PALETTE[v],
                    batch=self.batch, group=self.body_group))
        if border is not None and thick > 2:
            self.drawn.append(pyglet.shapes.Box(
                ox - thick, oy - thick, cell * w + 2 * thick,
                cell * h + 2 * thick, thickness=thick, color=border,
                batch=self.batch, group=self.top_group))

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        n = len(p.pairs)
        side = min(height / (n + 0.4) * 0.8, width * 0.16)
        for k, (a, b) in enumerate(p.pairs):
            y = bottom + height - (k + 1) * side * 1.2
            self._grid(a, left + width * 0.02, y, side)
            self._text('→', left + width * 0.02 + side * 1.25,
                       y + side / 2, calc_fontsize(20), bold=True)
            self._grid(b, left + width * 0.02 + side * 1.5, y, side)
        x0 = left + width * 0.42
        rest = width - (x0 - left)
        big = min(height * 0.42, rest * 0.3)
        y = bottom + height - big
        self._grid(p.test, x0 + (rest - big * 2.5) / 2, y, big)
        self._text('→  ?', x0 + (rest - big * 2.5) / 2 + big * 1.25,
                   y + big / 2, calc_fontsize(22), anchor='left', bold=True)
        m = len(p.cards)
        cs = min(rest / (m + 1) * 0.95, height * 0.4)
        gap = (rest - cs * m) / (m + 1)
        for k, g in enumerate(p.cards):
            x = x0 + gap + k * (cs + gap)
            border, thick = self._mark(k)
            self._grid(g, x, bottom, cs, border if thick > 2 else None,
                       thick)
            self._text(str(k + 1), x + cs / 2, bottom + cs + 14,
                       calc_fontsize(13), bold=True)
            self.hits.append((x, bottom, cs, cs, lambda c=k: self.choose(c)))
