# -*- coding: utf-8 -*-
"""Analogies on screen: A : B :: C : ?, and the candidates below.

For the agent boundary: port k picks candidate k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import analogy as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint
from .glyphtask import GlyphChoice, row


class Analogy(GlyphChoice):
    """A is to B as C is to which?"""

    instance: Optional['Analogy'] = None

    TITLE = 'Analogies'
    TASK_ID = 'analogies'
    PREFIX = 'ANALOGY'
    CATEGORY = 'reasoning'
    FOOTNOTE = _('click the candidate or press its number   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        lk = p.look
        top_h = height * 0.46
        y0 = bottom + height - top_h
        boxes = row(left, y0, width, top_h, 7, gap=0.01, most=0.92)
        size = calc_fontsize(26)
        for k, g in ((0, p.a), (2, p.b), (4, p.c)):
            x, y, s = boxes[k]
            glyphpaint.panel(self, lk, x, y, s, s)
            glyphpaint.glyph(self, lk, g, x, y, s, s)
            self._text('ABC'[k // 2], x + s * 0.08, y + s * 0.9,
                       calc_fontsize(12), anchor='left', bold=True,
                       colour=(90, 90, 100, 255))
        for k, words in ((1, ':'), (3, '::'), (5, ':')):
            x, y, s = boxes[k]
            self._text(words, x + s / 2, y + s / 2, size, bold=True)
        x, y, s = boxes[6]
        glyphpaint.panel(self, lk, x, y, s, s, paper=(228, 228, 232))
        self._text('?', x + s / 2, y + s / 2, size * 1.4, bold=True,
                   colour=(120, 120, 130, 255))
        self._candidates(lk, p.cards, left, bottom, width,
                         height - top_h - height * 0.04)
