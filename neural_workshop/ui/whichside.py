# -*- coding: utf-8 -*-
"""Which Side? on screen: examples left and right of a line, a new
panel below.

For the agent boundary: port 0 says left, 1 right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import whichside as model
from ..i18n import _
from . import glyphpaint
from .glyphtask import grid
from .oddoneout import draw_panel
from .spacetask import ChoiceTask


class WhichSide(ChoiceTask):
    """Does the new panel follow the left side's rule?"""

    instance: Optional['WhichSide'] = None

    TITLE = 'Which Side?'
    TASK_ID = 'which_side'
    PREFIX = 'SIDE'
    CATEGORY = 'reasoning'
    FOOTNOTE = _('Left / Right arrows, 1 / 2, or click   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _key(self, symbol: int, modifiers: int) -> None:
        pick = {key.LEFT: 0, key.RIGHT: 1}.get(symbol)
        if pick is not None:
            self.choose(pick)
            return
        super()._key(symbol, modifiers)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        lk = p.look
        top = height * 0.68
        y0 = bottom + height - top
        half = width / 2
        for side, panels, x0 in ((0, p.left, left), (1, p.right,
                                                     left + half)):
            n = len(panels)
            boxes = grid(x0 + half * 0.04, y0, half * 0.92, top, n,
                         3 if n > 4 else 2, 0.14)
            glyphpaint.panel(self, lk, x0 + half * 0.02, y0, half * 0.96,
                             top, paper=(236, 238, 244) if side else
                             (244, 240, 230))
            for panel, (x, y, s) in zip(panels, boxes):
                glyphpaint.panel(self, lk, x, y, s, s)
                draw_panel(self, lk, panel, x, y, s)
        self.drawn.append(pyglet.shapes.Line(
            left + half, y0 - 6, left + half, y0 + top + 6, thickness=4,
            color=self.ink, batch=self.batch, group=self.top_group))
        s = min(height - top - height * 0.06, width * 0.18)
        x, y = left + (width - s) / 2, bottom
        border, thick = (None, 2)
        if self.phase == 'judged':
            border, thick = ((60, 170, 90), 5) if self.chosen == p.answer \
                else ((214, 64, 58), 5)
        glyphpaint.panel(self, lk, x, y, s, s, border=border, thick=thick,
                         paper=(255, 255, 250))
        draw_panel(self, lk, p.query, x, y, s)
        self._text('?', x - s * 0.25, y + s / 2, s * 0.3, bold=True)
