# -*- coding: utf-8 -*-
"""Tangram on screen: the silhouette above, the sets of pieces below.

For the agent boundary: port k picks set k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import polyomino as P
from .. import tangram as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import polish, polypaint
from .spacetask import ChoiceTask


class Tangram(ChoiceTask):
    """Which pieces make the shape?"""

    instance: Optional['Tangram'] = None

    TITLE = 'Tangram'
    TASK_ID = 'tangram'
    PREFIX = 'TANGRAM'
    CATEGORY = 'perception'
    BUTTONS = 0
    FOOTNOTE = _('click a set or press its number   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        top = height * 0.42
        cell = polypaint.fit(p.shape, width * 0.5, top, 0.04)
        sh, sw = P.size_of(p.shape)
        polypaint.shape(self, p.shape, left + (width - sw * cell) / 2,
                        bottom + height - top + (top - sh * cell) / 2, cell,
                        (60, 60, 70), edge=(30, 30, 36))
        n = len(p.sets)
        bw = width / n * 0.92
        bh = height - top - height * 0.05
        gap = (width - bw * n) / (n + 1)
        for k, pieces in enumerate(p.sets):
            x = left + gap + k * (bw + gap)
            border, thick = self._mark(k)
            polish.card(self.drawn, self.batch, x, bottom, bw, bh,
                        (248, 246, 240), radius=10,
                        edge=border if thick > 2 else (200, 196, 190),
                        group=self.card_group)
            self._text(str(k + 1), x + 10, bottom + bh - 10,
                       calc_fontsize(12), anchor='left', anchor_y='top',
                       bold=True)
            self.hits.append((x, bottom, bw, bh, lambda c=k: self.choose(c)))
            # The pieces in a little grid inside the card.
            m = len(pieces)
            cols = 2 if m <= 4 else 3
            rows = (m + cols - 1) // cols
            cw, ch = bw / cols, (bh * 0.88) / rows
            c = min(polypaint.fit(q, cw, ch, 0.12) for q in pieces)
            c = min(c, cell * 0.8)
            for i, q in enumerate(pieces):
                qh, qw = P.size_of(q)
                px = x + (i % cols) * cw + (cw - qw * c) / 2
                py = bottom + bh * 0.88 - (i // cols + 1) * ch + \
                    (ch - qh * c) / 2
                polypaint.shape(self, q, px, py, c,
                                p.hues[i % len(p.hues)])
