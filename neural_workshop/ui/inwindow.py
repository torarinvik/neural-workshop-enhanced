# -*- coding: utf-8 -*-
"""In the Window on screen: a marker going round a ring or along a
track, with the window marked on its path.

Space presses. For the agent boundary: port 0 presses, port 1 waits.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import inwindow as model
from ..i18n import _
from .clocked import ClockedTask


class InTheWindow(ClockedTask):
    """Press while the marker is inside the window."""

    instance: Optional['InTheWindow'] = None

    TITLE = 'In the Window'
    TASK_ID = 'in_the_window'
    PREFIX = 'INTHEWINDOW'
    CATEGORY = 'first_steps'
    MODEL = model
    FEEDBACK = 1.2
    FOOTNOTE = _('Space: press   Esc: menu')
    EVENT_KEYS = {key.SPACE: model.PRESS}

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = self.run.dealt.question
        return ok

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d   %d/%d   window %d%% of the way round') % (
            self.rung, self.trial, self.total_trials,
            round(100 * self.run.dealt.share))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        d = run.dealt
        hue = model.HUES[d.hue]
        if self.dark:
            hue = tuple(min(255, c + 70) for c in hue)
        dim = (120, 124, 134) if self.dark else (176, 180, 190)
        fx, fy, scale = d.place
        if d.track == 'ring':
            r = min(width, height) * 0.4 * scale
            cx = left + r + (width - 2 * r) * fx
            cy = bottom + r + (height - 2 * r) * fy
            thick = max(6.0, r * 0.12)
            self.drawn.append(pyglet.shapes.Arc(
                cx, cy, r, thickness=thick, color=dim, batch=self.batch,
                group=self.card_group))
            self.drawn.append(pyglet.shapes.Arc(
                cx, cy, r, angle=360.0 * d.share,
                start_angle=360.0 * d.start, thickness=thick, color=hue,
                batch=self.batch, group=self.body_group))
            a = math.tau * run.at
            mx, my = cx + r * math.cos(a), cy + r * math.sin(a)
            size = thick * 0.9
        else:
            w = width * 0.86 * scale
            x0 = left + (width - w) * fx
            y = bottom + height * (0.2 + 0.6 * fy)
            thick = max(8.0, height * 0.05)
            self.drawn.append(pyglet.shapes.Rectangle(
                x0, y - thick / 2, w, thick, color=dim, batch=self.batch,
                group=self.card_group))
            end = d.start + d.share
            for a, b in ((d.start, min(1.0, end)), (0.0, end - 1.0)):
                if b > a:
                    self.drawn.append(pyglet.shapes.Rectangle(
                        x0 + a * w, y - thick / 2, (b - a) * w, thick,
                        color=hue, batch=self.batch,
                        group=self.body_group))
            mx, my = x0 + run.at * w, y
            size = thick * 0.9
        self.drawn.append(pyglet.shapes.Circle(
            mx, my, size, color=self.ink, batch=self.batch,
            group=self.text_group))
