# -*- coding: utf-8 -*-
"""Air Hockey on screen: the table from your end.

A white table with rails, the far goal and yours as dark mouths, your
mallet in red under the pointer and theirs in blue, the puck between
them, and the short bar that keeps your goal. The score is along the
top: yours of the goals you need, theirs of the goals that lose. On
the high rungs the camera swings round the table and at times looks
from the far end.

Mouse: your mallet goes where the pointer is on your half. Keys: Left
/ A and Right / D slide the bar across your goal.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; ports 14 and 15, held, slide the bar left
and right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import airhockey as model
from ..i18n import _
from . import polish
from .handtask import HandTask


class AirHockey(HandTask):
    """Score with one hand, keep goal with the other."""

    instance: Optional['AirHockey'] = None

    TITLE = 'Air Hockey'
    TASK_ID = 'air_hockey'
    PREFIX = 'HOCKEY'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    BACK = (20, 24, 40)
    FOOTNOTE = _('Mouse: your mallet   Left/Right or A/D: the bar in your '
                 'goal   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Score in the far goal; keep the puck out of yours')
        return ok

    def _held(self):
        k = self.keys
        if k[key.LEFT] or k[key.A]:
            return model.LEFT
        if k[key.RIGHT] or k[key.D]:
            return model.RIGHT
        return None

    def _puck(self, run, at, r, tall, colour) -> None:
        low, high = run.see(at), run.see(at, tall)
        side = run.see((at[0] + r, at[1]))
        if low is None or high is None or side is None:
            return
        rx = max(2.0, math.hypot(side[0] - low[0], side[1] - low[1]))
        ry = rx * 0.45
        dark = polish.mix((0, 0, 0), colour, 0.6)
        self.oval(low, rx, ry, dark, self.g())
        self.poly([(low[0] - rx, low[1]), (low[0] + rx, low[1]),
                   (high[0] + rx, high[1]), (high[0] - rx, high[1])], dark,
                  self.g())
        self.oval(high, rx, ry, colour, self.g())

    def _scene(self, run, s: float) -> None:
        m, level = model, run.level
        see = run.see
        self.rect(0, 0, 1000, 640, (26, 30, 50), self.g())
        for k in range(6):                                  # lamps
            self.disc((90 + 164 * k, 600), 16, (250, 240, 200, 90),
                      self.g())
        rim = 0.09
        self.poly([see((-1 - rim, -rim)), see((1 + rim, -rim)),
                   see((1 + rim, 2 + rim)), see((-1 - rim, 2 + rim))],
                  (60, 70, 110), self.g())
        self.poly([see((-1, 0)), see((1, 0)), see((1, 2)), see((-1, 2))],
                  (232, 238, 246), self.g())
        self.line(see((-1, 1)), see((1, 1)), 3, (214, 90, 90), self.g())
        ring = [see((0.3 * math.cos(a), 1 + 0.3 * math.sin(a)))
                for a in (math.pi * k / 12 for k in range(25))]
        for a, b in zip(ring, ring[1:]):
            self.line(a, b, 2, (214, 90, 90), self.g())
        for y, half in ((0.0, level.mouth), (2.0, m.THEIRS)):
            out = -rim if y == 0.0 else rim
            self.poly([see((-half, y)), see((half, y)), see((half, y + out)),
                       see((-half, y + out))], (16, 16, 24), self.g())
        things = [(m.PUCK, run.puck, 0.03, (30, 30, 36)),
                  (m.MALLET, run.mine, 0.09, (220, 60, 60)),
                  (m.MALLET, run.theirs, 0.09, (70, 110, 230))]
        far = run.far_end()
        things.sort(key=lambda t: t[1][1], reverse=not far)
        bar = [see((run.keeper - m.BAR, 0.03)), see((run.keeper + m.BAR,
                                                     0.03)),
               see((run.keeper + m.BAR, 0.09)), see((run.keeper - m.BAR,
                                                     0.09))]
        if far:
            self.poly(bar, (255, 190, 60), self.g())
        for r, at, tall, colour in things:
            if run.wait > 0 and r == m.PUCK and int(run.t * 6) % 2:
                continue
            self._puck(run, at, r, tall, colour)
        if not far:
            self.poly(bar, (255, 190, 60), self.g())
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        self.rect(330, 596, 340, 36, (12, 14, 24, 220), hud)
        self.words(_('you %d / %d') % (run.score[0], level.need), 420, 614,
                   15, bold=True, group=text, colour=(255, 130, 130, 255))
        self.words(_('them %d / %d') % (run.score[1], level.allow), 580,
                   614, 15, bold=True, group=text,
                   colour=(140, 170, 255, 255))
        if far:
            self.words(_('FROM THE FAR END'), 500, 572, 12, bold=True,
                       group=text, colour=(255, 220, 120, 255))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   first to %d') % (
            self.rung, self.trial, self.total_trials, run.level.need)
