# -*- coding: utf-8 -*-
"""Kerbside on screen: the street from above at night, you on it, and no
cars -- they are only heard.

Up (or W) walks forward, Down (or S) back. The white lines between
lanes are safe to stand on.

For the agent boundary: port 0 walks forward, port 1 back, for the step
it is sent in.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import kerbside as model
from ..i18n import _
from .livetask import LiveTask


class Kerbside(LiveTask):
    """Cross by ear."""

    instance: Optional['Kerbside'] = None

    TITLE = 'Kerbside'
    TASK_ID = 'kerbside'
    PREFIX = 'KERB'
    CATEGORY = 'attention'
    MODEL = model
    BACK = (14, 16, 22)
    FOOTNOTE = _('Up / W: walk   Down / S: step back   Listen   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Cross when the way is clear -- by ear')
        return ok

    def _held(self):
        k = self.keys
        if k[key.UP] or k[key.W]:
            return model.FORWARD
        if k[key.DOWN] or k[key.S]:
            return model.BACK
        return None

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height)
        lv = run.level
        span = model.far_side(lv) - model.START + 2.0
        k = (height - 40) / span
        k = min(k, (width - 40) / 30.0)

        def y_of(m):
            return bottom + 20 + (m - model.START + 1.0) * k

        x0, x1 = left + 20, left + width - 20
        cx = (x0 + x1) / 2
        g = self.layer()
        self.rect(x0, y_of(model.START - 1.0), x1 - x0, y_of(0) - y_of(
            model.START - 1.0), (52, 54, 60), g)
        self.rect(x0, y_of(0), x1 - x0, y_of(model.LANE * lv.lanes) - y_of(0),
                  (30, 32, 38), g)
        self.rect(x0, y_of(model.LANE * lv.lanes), x1 - x0,
                  y_of(model.far_side(lv) + 1.0) - y_of(model.LANE *
                                                         lv.lanes),
                  (52, 54, 60), g)
        g = self.layer()
        for i in range(lv.lanes + 1):
            y = y_of(model.LANE * i)
            edge = i in (0, lv.lanes)
            if edge:
                self.line((x0, y), (x1, y), 4, (200, 200, 190), g)
            else:
                x = x0
                while x < x1:
                    self.line((x, y), (min(x1, x + 24), y), 3,
                              (220, 220, 210), g)
                    x += 44
        for a, b in run.street.vans:
            self.rect(cx + a * k, y_of(-0.9), (b - a) * k, 0.8 * k,
                      (70, 80, 110), g)
        g = self.layer()
        self.disc((cx, y_of(run.y)), max(5.0, model.BODY * k * 1.6),
                  (250, 210, 120), g)
        self.disc((cx, y_of(run.y) + 0.25 * k), max(2.0, model.BODY * k * 0.6),
                  (60, 50, 40), g)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   %d lanes') % (
            self.rung, self.trial, self.total_trials, self.run.level.lanes)
