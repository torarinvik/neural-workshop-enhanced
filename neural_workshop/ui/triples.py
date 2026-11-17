# -*- coding: utf-8 -*-
"""Triples on screen: a pair and the candidates, or a table to count.

For the agent boundary: port k picks candidate k, or answers k triples.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import triples as model
from ..i18n import _
from . import glyphpaint
from .glyphtask import GlyphChoice, grid, row


class Triples(GlyphChoice):
    """All alike or all unlike, property by property."""

    instance: Optional['Triples'] = None

    TITLE = 'Triples'
    TASK_ID = 'triples'
    PREFIX = 'TRIPLES'
    CATEGORY = 'reasoning'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')

    def _make(self):
        p = model.deal(self.rung, rng=self.rng)
        self.BUTTONS = 0.13 if p.level.table else 0
        return p

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        lk = p.look
        if p.level.table:
            n = len(p.cards)
            for card, (x, y, s) in zip(p.cards, grid(
                    left, bottom, width, height, n, (n + 1) // 2, 0.1)):
                glyphpaint.panel(self, lk, x, y, s, s, paper=(255, 255, 252))
                glyphpaint.glyph(self, lk, model.glyph(card), x, y, s, s)
            return
        top = height * 0.45
        boxes = row(left, bottom + height - top, width, top, 3, gap=0.06)
        for k in range(3):
            x, y, s = boxes[k]
            if k < 2:
                glyphpaint.panel(self, lk, x, y, s, s, paper=(255, 255, 252))
                glyphpaint.glyph(self, lk, model.glyph(p.pair[k]), x, y, s, s)
            else:
                glyphpaint.panel(self, lk, x, y, s, s, paper=(228, 228, 232))
                self._text('?', x + s / 2, y + s / 2, s * 0.4, bold=True,
                           colour=(120, 120, 130, 255))
        self._candidates(lk, [model.glyph(c) for c in p.cards], left, bottom,
                         width, height - top - height * 0.05)
