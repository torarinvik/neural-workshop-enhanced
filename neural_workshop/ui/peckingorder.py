# -*- coding: utf-8 -*-
"""Pecking Order on screen: the clues as cards, the question below.

For the agent boundary: port 0 says the left one wins, 1 the right;
when the question is a creature's place, port k picks creature k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import peckingorder as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint
from .glyphtask import grid
from .spacetask import ChoiceTask


class PeckingOrder(ChoiceTask):
    """Who beats whom."""

    instance: Optional['PeckingOrder'] = None

    TITLE = 'Pecking Order'
    TASK_ID = 'pecking_order'
    PREFIX = 'PECKING'
    CATEGORY = 'reasoning'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')

    def _make(self):
        p = model.deal(self.rung, rng=self.rng)
        self.BUTTONS = 0 if p.level.place else 0.13
        return p

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        lk = p.look
        clue_h = height * (0.62 if p.level.place else 0.7)
        n = len(p.clues)
        cols = 2 if n > 4 else 1
        rows = (n + cols - 1) // cols
        ch = min(clue_h / rows, height * 0.16)
        cw = min(width / cols * 0.9, ch * 4.2)
        y0 = bottom + height - ch
        size = calc_fontsize(20)
        for k, (w, l, back) in enumerate(p.clues):
            col, row = k % cols, k // cols
            x = left + (width / cols) * col + (width / cols - cw) / 2
            y = y0 - row * ch
            glyphpaint.panel(self, lk, x, y + ch * 0.06, cw, ch * 0.88,
                             paper=(250, 250, 246))
            a, b = (l, w) if back else (w, l)
            s = ch * 0.8
            glyphpaint.glyph(self, lk, p.creatures[a], x + cw * 0.06,
                             y + ch * 0.1, s, s)
            glyphpaint.glyph(self, lk, p.creatures[b], x + cw * 0.94 - s,
                             y + ch * 0.1, s, s)
            self._text(_('loses to') if back else _('beats'), x + cw / 2,
                       y + ch / 2, size * 0.7, bold=True)
        rest = height - clue_h - height * 0.04
        if p.level.place:
            boxes = grid(left, bottom, width, rest, len(p.creatures),
                         len(p.creatures), 0.1)
            for k, (x, y, s) in enumerate(boxes):
                border, thick = self._mark(k)
                glyphpaint.panel(self, lk, x, y, s, s,
                                 border=border if thick > 2 else None,
                                 thick=thick)
                glyphpaint.glyph(self, lk, p.creatures[k], x, y, s, s)
                self._text(str(k + 1), x + s * 0.1, y + s * 0.88,
                           calc_fontsize(10), anchor='left', bold=True)
                self.hits.append((x, y, s, s, lambda c=k: self.choose(c)))
            return
        s = min(rest * 0.9, width * 0.14)
        y = bottom + (rest - s) / 2
        for k, c in enumerate(p.pair):
            x = left + width / 2 + (-1.4 if k == 0 else 0.4) * s
            border, thick = self._mark(k)
            glyphpaint.panel(self, lk, x, y, s, s,
                             border=border if thick > 2 else None,
                             thick=thick)
            glyphpaint.glyph(self, lk, p.creatures[c], x, y, s, s)
            self.hits.append((x, y, s, s, lambda c=k: self.choose(c)))
        self._text(_('vs'), left + width / 2, y + s / 2, size, bold=True)
