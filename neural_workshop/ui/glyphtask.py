# -*- coding: utf-8 -*-
"""What the glyph tasks' screens share: rows of glyph panels.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from ..geometry import calc_fontsize
from . import glyphpaint
from .spacetask import ChoiceTask


def row(left, bottom, width, height, n: int, gap: float = 0.04,
        most: float = 0.9) -> List[Tuple[float, float, float]]:
    """Square boxes for *n* panels across a strip: (x, y, side)."""
    side = min(height * most, width * (1 - gap * (n + 1)) / max(1, n))
    space = (width - side * n) / (n + 1)
    y = bottom + (height - side) / 2
    return [(left + space + k * (side + space), y, side) for k in range(n)]


def grid(left, bottom, width, height, n: int, cols: int,
         gap: float = 0.08) -> List[Tuple[float, float, float]]:
    """Square boxes for *n* panels in rows of *cols*."""
    rows = (n + cols - 1) // cols
    side = min(width / (cols + gap * (cols + 1)),
               height / (rows + gap * (rows + 1)))
    space = side * gap
    w = cols * side + (cols - 1) * space
    h = rows * side + (rows - 1) * space
    x0 = left + (width - w) / 2
    y0 = bottom + (height + h) / 2 - side
    return [(x0 + (k % cols) * (side + space),
             y0 - (k // cols) * (side + space), side) for k in range(n)]


class GlyphChoice(ChoiceTask):
    """A choice task whose candidates are glyph panels."""

    BUTTONS = 0

    def _candidates(self, lk, cards: Sequence, left, bottom, width,
                    height) -> None:
        cols = len(cards) if len(cards) <= 5 else (len(cards) + 1) // 2
        boxes = grid(left, bottom, width, height, len(cards), cols, 0.12)
        for k, (g, (x, y, s)) in enumerate(zip(cards, boxes)):
            border, thick = self._mark(k)
            glyphpaint.panel(self, lk, x, y, s, s,
                             border=border if thick > 2 else None,
                             thick=thick)
            glyphpaint.glyph(self, lk, g, x, y, s, s)
            self._text(str(k + 1), x + s * 0.08, y + s * 0.9,
                       calc_fontsize(12), anchor='left', bold=True,
                       colour=(90, 90, 100, 255))
            self.hits.append((x, y, s, s, lambda c=k: self.choose(c)))
