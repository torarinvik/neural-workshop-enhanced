# -*- coding: utf-8 -*-
"""Longer or Sooner? on screen: lamps that light, or a speaker while
the tones play.

For the agent boundary: port 0 says the first (or the left), 1 the
second (or the right). The tones reach the agent only as sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import howlong as model
from ..i18n import _
from . import polish
from .showtask import ShowTask

OFF = (70, 72, 80)


class HowLong(ShowTask):
    """Which lasted longer; which came first?"""

    instance: Optional['HowLong'] = None

    TITLE = 'Longer or Sooner?'
    TASK_ID = 'longer_or_sooner'
    PREFIX = 'HOWLONG'
    CATEGORY = 'perception'
    FOOTNOTE = _('1 / 2 or click   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        w, h = min(width * 0.8, height * 1.8), min(height, width * 0.45)
        x0, y0 = left + (width - w) / 2, bottom + (height - h) / 2
        polish.card(self.drawn, self.batch, x0, y0, w, h, (34, 36, 44),
                    radius=16, group=self.card_group)
        if p.guise == 'tone':
            self._text(_('listen'), x0 + w / 2, y0 + h / 2, h * 0.12,
                       colour=(200, 200, 210, 255))
            return
        on = model.lit(p, t)
        r = h * 0.22
        spots = [(x0 + w / 2, y0 + h / 2)] if p.kind == 'longer' else \
            [(x0 + w * 0.28, y0 + h / 2), (x0 + w * 0.72, y0 + h / 2)]
        for k, (cx, cy) in enumerate(spots):
            ev = [e for e in on if (p.kind == 'longer' or e.side == k)]
            big = r * (1.25 if ev and ev[0].strong else 1.0)
            colour = (polish.lighter(p.hue, 0.25) if ev and ev[0].strong
                      else p.hue) if ev else OFF
            self.drawn.append(pyglet.shapes.Circle(
                cx, cy, big if ev else r, color=colour, batch=self.batch,
                group=self.body_group))
