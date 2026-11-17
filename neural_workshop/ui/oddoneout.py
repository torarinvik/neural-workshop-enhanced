# -*- coding: utf-8 -*-
"""Odd One Out on screen: a row of panels; click the odd one.

For the agent boundary: port k picks panel k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import oddoneout as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint
from .glyphtask import GlyphChoice, grid


def draw_panel(task, lk, panel, x, y, s) -> None:
    """One glyph, or a pair side by side."""
    if len(panel) == 1:
        glyphpaint.glyph(task, lk, panel[0], x, y, s, s)
    else:
        glyphpaint.glyph(task, lk, panel[0], x, y + s * 0.2, s / 2, s * 0.6)
        glyphpaint.glyph(task, lk, panel[1], x + s / 2, y + s * 0.2, s / 2,
                         s * 0.6)


class OddOneOut(GlyphChoice):
    """All but one share something; which one?"""

    instance: Optional['OddOneOut'] = None

    TITLE = 'Odd One Out'
    TASK_ID = 'odd_one_out'
    PREFIX = 'ODDONE'
    CATEGORY = 'reasoning'
    FOOTNOTE = _('click the odd one or press its number   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        n = len(p.panels)
        cols = n if n <= 5 else (n + 1) // 2
        for k, (x, y, s) in enumerate(grid(left, bottom, width, height, n,
                                           cols, 0.12)):
            border, thick = self._mark(k)
            glyphpaint.panel(self, p.look, x, y, s, s,
                             border=border if thick > 2 else None,
                             thick=thick)
            draw_panel(self, p.look, p.panels[k], x, y, s)
            self._text(str(k + 1), x + s * 0.08, y + s * 0.9,
                       calc_fontsize(12), anchor='left', bold=True,
                       colour=(90, 90, 100, 255))
            self.hits.append((x, y, s, s, lambda c=k: self.choose(c)))
