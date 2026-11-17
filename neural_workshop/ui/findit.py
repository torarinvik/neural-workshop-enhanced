# -*- coding: utf-8 -*-
"""Find It on screen: the target above, the crowd below, then a cover.

For the agent boundary: port 0 says yes, 1 no.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import findit as model
from ..i18n import _
from . import glyphpaint, polish
from .showtask import ShowTask


class FindIt(ShowTask):
    """Was the target among them?"""

    instance: Optional['FindIt'] = None

    TITLE = 'Find It'
    TASK_ID = 'find_it'
    PREFIX = 'FINDIT'
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

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        lk = p.look
        ts = height * 0.18
        tx = left + width / 2 - ts / 2
        glyphpaint.panel(self, lk, tx, bottom + height - ts, ts, ts,
                         paper=(255, 255, 255))
        glyphpaint.glyph(self, lk, p.target, tx, bottom + height - ts, ts, ts)
        self._text(_('Target'), tx - 10, bottom + height - ts / 2, ts * 0.18,
                   anchor='right', bold=True)
        side = min(width, height - ts - height * 0.04)
        x0, y0 = left + (width - side) / 2, bottom
        glyphpaint.panel(self, lk, x0, y0, side, side)
        if t >= p.level.show and self.phase == self.PLAY:
            polish.rounded(self.drawn, self.batch, x0, y0, side, side,
                           (150, 150, 160), radius=12, group=self.body_group)
            return
        n = int((p.level.items * 1.5) ** 0.5) + 1
        cell = side / n * 1.5
        for it in p.items:
            glyphpaint.glyph(self, lk, it.glyph, x0 + it.x * side - cell / 2,
                             y0 + it.y * side - cell / 2, cell, cell)
