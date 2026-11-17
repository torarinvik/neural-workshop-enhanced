# -*- coding: utf-8 -*-
"""Behind the Screen on screen: a stage, its screen or screens, the
balls rolling.

For the agent boundary: port k answers k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import behindscreen as model
from ..i18n import _
from . import polish
from .showtask import ShowTask

STAGE = (232, 222, 200)
SCREEN = (120, 70, 60)


class BehindScreen(ShowTask):
    """How many are behind the screen now?"""

    instance: Optional['BehindScreen'] = None

    TITLE = 'Behind the Screen'
    TASK_ID = 'behind_the_screen'
    PREFIX = 'BEHIND'
    CATEGORY = 'perception'
    FOOTNOTE = _('press the number (1 for none, 2 for one...) or click   '
                 'Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        w, h = width * 0.94, height * 0.9
        x0, y0 = left + (width - w) / 2, bottom + (height - h) / 2
        polish.card(self.drawn, self.batch, x0, y0, w, h, STAGE, radius=12,
                    group=self.card_group)
        r = h * 0.045
        for b in p.balls:
            x = model.where(b, t)
            if 0.0 < x < 1.0:
                self.drawn.append(pyglet.shapes.Circle(
                    x0 + x * w, y0 + b.lane * h, r,
                    color=p.hues[b.colour], batch=self.batch,
                    group=self.body_group))
        for k, (a, b) in enumerate(p.screens):
            colour = SCREEN
            if self.phase == 'judged' and k == p.asked_screen:
                colour = polish.lighter(SCREEN, 0.15)
            polish.rounded(self.drawn, self.batch, x0 + a * w, y0 + h * 0.04,
                           (b - a) * w, h * 0.92, colour, radius=6,
                           group=self.top_group)
        # Off the stage's sides, curtains.
        for cx in (x0, x0 + w * 0.95):
            polish.rounded(self.drawn, self.batch, cx, y0, w * 0.05, h,
                           (150, 40, 50), radius=4, group=self.top_group)
        if p.asked_colour >= 0 and (self.run is None or self.run.open):
            self.drawn.append(pyglet.shapes.Circle(
                left + width / 2, y0 - 4, r, color=p.hues[p.asked_colour],
                batch=self.batch, group=self.top_group))
