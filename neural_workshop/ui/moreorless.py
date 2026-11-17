# -*- coding: utf-8 -*-
"""More or Less on screen: the dots flash and are covered; or two
columns, matched, and one moves.

For the agent boundary: port 0 says left, 1 right, 2 the same.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import moreorless as model
from ..i18n import _
from . import polish
from .showtask import ShowTask

PAPER = (248, 246, 240)
COVER = (150, 150, 160)


class MoreOrLess(ShowTask):
    """Which has more, at a glance?"""

    instance: Optional['MoreOrLess'] = None

    TITLE = 'More or Less'
    TASK_ID = 'more_or_less'
    PREFIX = 'MORELESS'
    CATEGORY = 'perception'
    FOOTNOTE = _('1: left   2: right   3: the same   (or click)   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        side = min(width * 0.9, height * 1.6)
        w, h = side, side / 1.6
        x0, y0 = left + (width - w) / 2, bottom + (height - h) / 2
        polish.card(self.drawn, self.batch, x0, y0, w, h, PAPER, radius=14,
                    group=self.card_group)
        if p.kind == 'rows':
            for s in (model.LEFT, model.RIGHT):
                for k in range(p.rows[s]):
                    x, y = model.row_place(p, s, k, t)
                    self.drawn.append(pyglet.shapes.Circle(
                        x0 + x * w, y0 + y * h, h * 0.035,
                        color=p.hues[s], batch=self.batch,
                        group=self.body_group))
            return
        if t >= p.level.flash and self.phase == self.PLAY:
            polish.rounded(self.drawn, self.batch, x0, y0, w, h, COVER,
                           radius=14, group=self.body_group)
            self._text('?', x0 + w / 2, y0 + h / 2, h * 0.3, bold=True,
                       colour=(240, 240, 245, 255))
            return
        if not p.level.mixed:
            self.drawn.append(pyglet.shapes.Line(
                x0 + w / 2, y0 + 8, x0 + w / 2, y0 + h - 8, thickness=2,
                color=(200, 200, 200), batch=self.batch,
                group=self.body_group))
        for d in p.dots:
            self.drawn.append(pyglet.shapes.Circle(
                x0 + d.x * w, y0 + d.y * h, max(1.5, d.r * w * 0.62),
                color=p.hues[d.side], batch=self.batch,
                group=self.top_group))
        if p.level.mixed:
            for s in (0, 1):
                self.drawn.append(pyglet.shapes.Circle(
                    x0 + (0.1 if s == 0 else 0.9) * w, y0 - 16, 9,
                    color=p.hues[s], batch=self.batch, group=self.top_group))
