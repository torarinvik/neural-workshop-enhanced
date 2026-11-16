# -*- coding: utf-8 -*-
"""Sign Painter on screen: a board on two chains, and a wet brush.

The board hangs from the beam and, from the middle rungs, swings; the
letters to paint are a pale outline on it, or only their corners, or
nothing, by rung. What you have painted stays in its colour. The order
is along the top; the pots along the bottom are the four colours, with
how much paint the brush still holds.

Mouse: hold the button and draw each stroke from its start. Keys: 1-4
(or R, G, B, Y) pick a colour, Space dips the brush.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14-17 pick red, green, blue and yellow and
18 dips the brush.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import signpainter as model
from ..i18n import _
from .handtask import HandTask

PAINT = ((214, 60, 54), (60, 170, 90), (70, 110, 220), (240, 200, 60))
PLAIN = (40, 36, 40)


class SignPainter(HandTask):
    """Paint the word, stroke by stroke."""

    instance: Optional['SignPainter'] = None

    TITLE = 'Sign Painter'
    TASK_ID = 'sign_painter'
    PREFIX = 'SIGN'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key._1: model.RED, key._2: model.RED + 1,
                  key._3: model.RED + 2, key._4: model.RED + 3,
                  key.R: model.RED, key.G: model.RED + 1,
                  key.B: model.RED + 2, key.Y: model.RED + 3,
                  key.SPACE: model.DIP}
    BACK = (52, 60, 70)
    FOOTNOTE = _('Hold the button and paint each stroke   1-4: colour   '
                 'Space: dip the brush   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = self.run.sign.order
        return ok

    def _scene(self, run, s: float) -> None:
        m, sign, level = model, run.sign, run.level
        wide, tall = m.BOARD
        self.rect(0, 0, 1000, 640, (96, 110, 124), self.g())
        for k in range(9):                                  # the wall
            self.rect(0, 70 * k, 1000, 2, (84, 98, 112), self.g())
        self.rect(0, 0, 1000, 70, (70, 60, 54), self.g())
        self.rect(60, 596, 880, 18, (70, 50, 40), self.g())  # the beam
        see = run.see
        for u in (0.6, wide - 0.6):
            top = see(u, tall)
            if top is not None:
                self.line((top[0], 596), top, 3, (40, 40, 46), self.g())
        back = [see(-0.15, -0.15, -0.12), see(wide + 0.15, -0.15, -0.12),
                see(wide + 0.15, tall + 0.15, -0.12),
                see(-0.15, tall + 0.15, -0.12)]
        self.poly(back, (60, 44, 34), self.g())
        self.poly([see(0, 0), see(wide, 0), see(wide, tall), see(0, tall)],
                  (236, 226, 200), self.g())
        if level.guide == 'outline':
            for line in sign.strokes:
                for a, b in zip(line, line[1:]):
                    self.line(see(*a), see(*b), 9, (206, 196, 172),
                              self.g())
        elif level.guide == 'corners':
            for c in sign.corners:
                self.disc(see(*c), 3.5, (170, 160, 140), self.g())
        ink = PAINT[sign.colour] if sign.colour >= 0 else PLAIN
        for n, line in enumerate(sign.strokes[:run.stroke + 1]):
            upto = len(line) if n < run.stroke else run.point
            for a, b in zip(line[:upto], line[1:upto]):
                self.line(see(*a), see(*b), 9, ink, self.g())
            for p in line[:upto]:
                self.disc(see(*p), 4.5, ink, self.g())
        goal = run.goal
        if goal is not None and level.rung < 7:
            self.disc(see(*goal), 7, (255, 255, 255, 200), self.g())
            self.disc(see(*goal), 4, (236, 80, 64), self.g())
        if run.brush is not None:
            self.disc(see(*run.brush), 6,
                      PAINT[run.colour] if run.colour >= 0 else PLAIN,
                      self.g())
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        self.rect(200, 618, 600, 22, (16, 18, 28, 200), hud)
        self.words(sign.order, 500, 629, 13, bold=True, group=text,
                   colour=(255, 255, 255, 255))
        if level.colour:
            for k in range(4):
                x = 320 + 120 * k
                self.rect(x - 34, 8, 68, 52, (40, 36, 34), hud)
                self.rect(x - 28, 14, 56, 34, PAINT[k], text)
                if run.colour == k:
                    self.rect(x - 34, 60, 68, 5, (255, 255, 255), text)
                self.words('%d' % (k + 1), x, 31, 13, bold=True,
                           group=pyglet.graphics.Group(order=902),
                           colour=(20, 20, 20, 255))
        if level.load:
            share = max(0.0, min(1.0, run.paint / float(level.load)))
            self.words(_('paint'), 60, 40, 11, group=text,
                       colour=(240, 240, 240, 255))
            self.rect(90, 34, 110, 12, (40, 36, 34), hud)
            self.rect(90, 34, 110 * share, 12, (236, 80, 64)
                      if share < 0.2 else (240, 240, 240), text)
        for k in range(3):
            self.disc((880 + 26 * k, 40), 8, (236, 80, 64)
                      if k < run.smudges else (50, 46, 44), text)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %s') % (
            self.rung, self.trial, self.total_trials, run.sign.word)
