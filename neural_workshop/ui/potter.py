# -*- coding: utf-8 -*-
"""Potter's Wheel on screen: the clay turning, your hands on it.

The clay stands on the wheel, a band for each height, streaks going
round it as it spins. The pot wanted is a pale outline over the clay,
or a drawing beside it, or gone after a moment, by rung. A band that is
right shows a green mark at its side. The corner has the wheel's speed
and how wet the clay is.

Mouse: hold the button and press in from the side to narrow a band,
draw out to widen it. Keys: Up / W faster, Down / S slower, Space wets
the clay.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 spins the wheel faster, 15 slower, 16
wets the clay.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import potter as model
from ..i18n import _
from . import polish
from .handtask import HandTask

CLAY = (176, 112, 78)


class PottersWheel(HandTask):
    """Throw the pot that is asked for."""

    instance: Optional['PottersWheel'] = None

    TITLE = "Potter's Wheel"
    TASK_ID = 'potters_wheel'
    PREFIX = 'POTTER'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.UP: model.FASTER, key.W: model.FASTER,
                  key.DOWN: model.SLOWER, key.S: model.SLOWER,
                  key.SPACE: model.WET}
    BACK = (44, 36, 34)
    FOOTNOTE = _('Hold the button and press the clay in or draw it out   '
                 'Up/Down: wheel speed   Space: wet the clay   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Shape the clay to the pot shown, then let go')
        return ok

    def _pot(self, radii, cx, foot, tall, unit, colour, turn=None) -> None:
        n = len(radii)
        for k, r in enumerate(radii):
            y0, y1 = foot + tall * k / n, foot + tall * (k + 1) / n
            below = radii[k - 1] if k else r
            lo = (r + below) / 2 * unit
            hi = ((r + radii[k + 1]) / 2 if k + 1 < n else r) * unit
            for a, b, shade in ((-1.0, -0.55, 0.62), (-0.55, 0.25, 0.86),
                                (0.25, 0.6, 1.0), (0.6, 1.0, 0.78)):
                self.poly([(cx + a * lo, y0), (cx + b * lo, y0),
                           (cx + b * hi, y1), (cx + a * hi, y1)],
                          polish.mix((0, 0, 0), colour, shade), self.g())
            if turn is not None:
                for i in range(3):
                    at = turn + 2.1 * i + 0.4 * k
                    if math.sin(at) > 0:
                        x = math.cos(at)
                        self.line((cx + x * lo, y0), (cx + x * hi, y1), 2,
                                  polish.mix((0, 0, 0), colour, 0.7),
                                  self.g())
        top = radii[-1] * unit
        self.oval((cx, foot + tall), top, max(3.0, top * 0.16),
                  polish.mix((0, 0, 0), colour, 0.45), self.g())

    def _scene(self, run, s: float) -> None:
        m, level = model, run.level
        self.rect(0, 0, 1000, 640, (58, 48, 46), self.g())
        self.rect(0, 0, 1000, 150, (88, 66, 50), self.g())      # the bench
        for k in range(5):                                      # shelves
            self.rect(40 + 190 * k, 560, 150, 8, (96, 72, 54), self.g())
            self.oval((115 + 190 * k, 590), 26 + 6 * (k % 2), 24,
                      (120 + 12 * k, 86, 70), self.g())
        self.oval((m.AXIS, m.FOOT - 14), 250, 40, (40, 40, 46), self.g())
        self.oval((m.AXIS, m.FOOT - 4), 240, 36, (120, 120, 128), self.g())
        for i in range(8):                                      # it turns
            a = run.turn + math.pi * i / 4
            self.line((m.AXIS + 150 * math.cos(a), m.FOOT - 4
                       + 22 * math.sin(a)),
                      (m.AXIS + 236 * math.cos(a), m.FOOT - 4
                       + 35 * math.sin(a)), 2, (96, 96, 104), self.g())
        wet = polish.mix((150, 130, 120), CLAY, run.wet)
        self._pot(run.r, m.AXIS, m.FOOT, m.TALL, m.UNIT, wet, run.turn)
        n = level.bands
        if run.shown():
            if level.ghost == 'over':
                for k, want in enumerate(run.pot.shape):
                    y0 = m.FOOT + m.TALL * k / n
                    y1 = m.FOOT + m.TALL * (k + 1) / n
                    for side in (-1, 1):
                        x = m.AXIS + side * want * m.UNIT
                        self.line((x, y0 + 2), (x, y1 - 2), 3,
                                  (255, 255, 255, 190), self.g())
            else:
                self.rect(770, 300, 200, 250, (30, 26, 26, 230), self.g())
                self._pot(run.pot.shape, 870, 330, 170, 70, (210, 200, 190))
                self.words(_('wanted'), 870, 315, 11, group=self.g(),
                           colour=(230, 230, 230, 255))
        if level.rung < 7:
            for k in range(n):
                good = run.was_near[k]
                self.disc((m.AXIS + 1.35 * m.UNIT, m.band_y(n, k)), 6,
                          (110, 220, 140) if good else (90, 80, 80),
                          self.g())
        if run.hand.down and run.touching is not None:
            self.disc((run.hand.x, run.hand.y), 16, (236, 200, 170, 230),
                      self.g())
        hud = pyglet.graphics.Group(order=900)
        self.words(_('wheel'), 60, 520, 12, group=hud,
                   colour=(230, 230, 230, 255))
        for k in range(3):
            self.disc((110 + 22 * k, 520), 7, (255, 200, 70)
                      if k < run.speed else (90, 80, 80), hud)
        if level.dry:
            self.words(_('wet'), 60, 492, 12, group=hud,
                       colour=(230, 230, 230, 255))
            self.rect(100, 486, 90, 10, (70, 60, 60), hud)
            self.rect(100, 486, 90 * run.wet, 10, (90, 170, 240)
                      if run.wet > 0.25 else (236, 80, 64), hud)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d bands') % (
            self.rung, self.trial, self.total_trials, run.level.bands)
