# -*- coding: utf-8 -*-
"""Lock Pick on screen: the lock cut open, the pick under the pins.

The lock is drawn in section: a brass body, a row of pin chambers with
their springs, and your pick coming in along the keyway. A set pin
stays up and turns green. On the easy rungs the pin that binds glows;
on the hard ones the pins are not drawn at all and the lock is worked
by ear. The gauge at the right is the tension on the wrench, with the
band it has to stay in.

Mouse: put the pick's tip under a pin, hold the button and lift.
Keys: hold Space (or T) for tension.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; port 14, held, tightens the wrench.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import lockpick as model
from ..i18n import _
from .handtask import HandTask

BRASS = (190, 150, 70)


class LockPick(HandTask):
    """Set every pin."""

    instance: Optional['LockPick'] = None

    TITLE = 'Lock Pick'
    TASK_ID = 'lock_pick'
    PREFIX = 'PICK'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    BACK = (24, 26, 34)
    DRAW_POINTER = False
    FOOTNOTE = _('Hold Space: tension   Hold the button under a pin and '
                 'lift it until it sets   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Keep the tension in the band and set each pin')
        return ok

    def _held(self):
        k = self.keys
        return model.TENSION if k[key.SPACE] or k[key.T] else None

    def _scene(self, run, s: float) -> None:
        m, level = model, run.level
        n = level.pins
        left, right = m.LEFT - 70, m.pin_x(n - 1) + 70
        self.rect(left - 30, 150, right - left + 60, 440, (60, 62, 74),
                  self.g())
        self.rect(left, 180, right - left, 390, BRASS, self.g())
        self.rect(left, 180, right - left, m.FLOOR - 180, (150, 116, 50),
                  self.g())                                 # the plug
        self.rect(left - 30, m.FLOOR - 26, right - left + 30, 26,
                  (20, 20, 26), self.g())                   # the keyway
        shear = m.FLOOR + m.LIFT + 62
        for k in range(n):
            x = m.pin_x(k)
            self.rect(x - 17, m.FLOOR, 34, 330, (36, 34, 40), self.g())
            if level.hidden:
                continue
            base = m.FLOOR + run.lift[k] * m.LIFT
            done = run.is_set(k)
            colour = (110, 220, 140) if done else (236, 200, 90)
            self.poly([(x - 14, base + 10), (x, base), (x + 14, base + 10),
                       (x + 14, base + 60), (x - 14, base + 60)], colour,
                      self.g())
            self.rect(x - 14, base + 64, 28, 46, (170, 174, 190), self.g())
            top = m.FLOOR + 326
            for j in range(6):                              # the spring
                y0 = base + 112 + (top - base - 112) * j / 6.0
                y1 = base + 112 + (top - base - 112) * (j + 1) / 6.0
                self.line((x - 10 + 20 * (j % 2), y0),
                          (x + 10 - 20 * (j % 2), y1), 2, (200, 200, 210),
                          self.g())
            if level.glow and k == run.binding:
                for dx in (-19, 17):
                    self.rect(x + dx, m.FLOOR, 2, 330, (255, 220, 90),
                              self.g())
        self.line((left, shear), (right, shear), 1, (90, 70, 30), self.g())
        tip = (run.hand.x, run.hand.y)                      # the pick
        self.line((left - 200, m.FLOOR - 40), (tip[0] - 14, tip[1] - 14),
                  5, (210, 214, 226), self.g())
        self.line((tip[0] - 14, tip[1] - 14), tip, 5,
                  (255, 220, 120) if run.hand.down else (210, 214, 226),
                  self.g())
        hud = pyglet.graphics.Group(order=900)
        gx = 900
        self.rect(gx, 200, 30, 300, (40, 42, 54), hud)
        lo, hi = level.band
        self.rect(gx, 200 + 300 * lo, 30, 300 * (hi - lo), (60, 130, 80),
                  hud)
        self.rect(gx, 200 + 300 * 0.97, 30, 9, (236, 80, 64), hud)
        self.rect(gx - 8, 196 + 300 * run.tension, 46, 8, (255, 255, 255),
                  hud)
        self.words(_('tension'), gx + 15, 180, 12, group=hud,
                   colour=(230, 230, 230, 255))
        for k in range(3):
            self.disc((gx - 8 + 23 * k, 530), 7, (236, 80, 64)
                      if k < run.slips else (70, 72, 84), hud)
        self.words(_('%d of %d set') % (run.set, n), 500, 612, 14,
                   bold=True, group=hud, colour=(255, 255, 255, 255))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d pins') % (
            self.rung, self.trial, self.total_trials, run.level.pins)
