# -*- coding: utf-8 -*-
"""Which Urn? on screen: two kinds of urn, how many of each, the draw.

For the agent boundary: port 0 says the left kind, 1 the right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import urns as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import polish
from .spacetask import ChoiceTask


class Urns(ChoiceTask):
    """From which kind of urn, more likely?"""

    instance: Optional['Urns'] = None

    TITLE = 'Which Urn?'
    TASK_ID = 'which_urn'
    PREFIX = 'URNS'
    CATEGORY = 'reasoning'
    FOOTNOTE = _('1 / 2 or click   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _urn(self, balls, x, y, w, h) -> None:
        polish.card(self.drawn, self.batch, x, y, w, h, (236, 240, 246),
                    radius=w * 0.3, edge=(150, 160, 180), group=self.card_group)
        flat = [c for c, n in enumerate(balls) for _k in range(n)]
        cols = 4
        r = min(w / (cols * 2.4), h / (((len(flat) + cols - 1) // cols) * 2.6))
        for k, c in enumerate(flat):
            cx = x + w / 2 + ((k % cols) - (cols - 1) / 2) * r * 2.3
            cy = y + r * 1.6 + (k // cols) * r * 2.3
            self.drawn.append(pyglet.shapes.Circle(
                cx, cy, r, color=model.COLOURS[c], batch=self.batch,
                group=self.top_group))

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        top_h = height * 0.62
        for side in (0, 1):
            x0 = left + side * width / 2
            n = p.copies[side]
            w = min(width / 2 / (n + 1), top_h * 0.5)
            for k in range(n):
                x = x0 + width / 4 - (n * w * 1.1) / 2 + k * w * 1.1
                self._urn(p.urns[side], x, bottom + height - top_h, w,
                          top_h * 0.9)
            words = _('Left kind') if side == 0 else _('Right kind')
            if n > 1:
                words += '  ×%d' % n
            self._text(words, x0 + width / 4, bottom + height - top_h - 14,
                       calc_fontsize(13), bold=True)
        # The draw.
        k = len(p.drawn)
        r = min(width / (k * 2.8 + 2), height * 0.07)
        y = bottom + (height - top_h) * 0.45
        self._text(_('Drawn:') if p.level.replace else
                   _('Drawn, not put back:'), left + width / 2,
                   y + r * 2.2, calc_fontsize(13))
        for i, c in enumerate(p.drawn):
            cx = left + width / 2 + (i - (k - 1) / 2) * r * 2.6
            self.drawn.append(pyglet.shapes.Circle(
                cx, y, r, color=model.COLOURS[c], batch=self.batch,
                group=self.top_group))
