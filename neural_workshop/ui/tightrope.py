# -*- coding: utf-8 -*-
"""Tightrope on screen: the walker, the pole, and a long way down.

You see the walker from behind, on a wire that runs away to the far
tower, the street far below. The walker leans as the model's lean
says; the pole slides out to the side the pointer is on. Wind shows as
streaks across the sky, and a bird that lands on the pole sits where
it has to be clicked off. Along the top is how far across you are.

Mouse: left and right carries the pole; click a bird to shoo it.
Keys: Space (or Up, or W) takes a step.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 takes a step.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import tightrope as model
from ..i18n import _
from . import polish
from .handtask import HandTask


class Tightrope(HandTask):
    """Step by step across, upright."""

    instance: Optional['Tightrope'] = None

    TITLE = 'Tightrope'
    TASK_ID = 'tightrope'
    PREFIX = 'ROPE'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.SPACE: model.STEP, key.UP: model.STEP,
                  key.W: model.STEP}
    BACK = (30, 40, 70)
    FOOTNOTE = _('Mouse left and right: the pole   Space: a step   '
                 'Click a bird to shoo it   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Walk across: balance with the pole')
        return ok

    def _scene(self, run, s: float) -> None:
        level = run.level
        share = run.taken / max(1, level.steps)
        for k in range(8):                                  # the sky
            self.rect(0, 80 * k, 1000, 80,
                      polish.mix((250, 170, 120), (40, 60, 120), k / 7.0),
                      self.g())
        for k in range(14):                                 # the street
            x = (k * 83 + 40 - 30 * share * (1 + k % 3)) % 1080 - 40
            tall = 40 + 37 * (k * 7 % 5)
            self.rect(x, 0, 60, tall, polish.mix((20, 24, 40), (60, 70, 100),
                                                 (k % 4) / 4.0), self.g())
            for w in range(int(tall // 22)):
                self.rect(x + 10 + 26 * (w % 2), 10 + 20 * w, 8, 8,
                          (250, 220, 120, 200), self.g())
        size = 0.35 + 0.65 * share                          # the far tower
        self.rect(500 - 60 * size, 330, 120 * size, 200 * size,
                  (50, 50, 70), self.g())
        self.rect(500 - 80 * size, 330 - 8 * size, 160 * size, 12 * size,
                  (200, 80, 70), self.g())
        self.poly([(494, 150), (506, 150), (501.5, 330), (498.5, 330)],
                  (30, 30, 36), self.g())                   # the wire
        self.poly([(470, 0), (530, 0), (506, 150), (494, 150)],
                  (30, 30, 36), self.g())
        blow = run.wind()
        if blow:
            for k in range(9):
                y = 200 + 45 * k
                x = (run.t * 700 * (1 if blow > 0 else -1) + 137 * k) % 1200
                self.line((x - 100, y), (x - 20, y), 2,
                          (255, 255, 255, 150), self.g())
        lean = run.lean
        foot = (500.0, 150.0)

        def up(d: float, side: float = 0.0):
            return (foot[0] + d * math.sin(lean) + side * math.cos(lean),
                    foot[1] + d * math.cos(lean) - side * math.sin(lean))
        for side in (-1, 1):                                # legs
            self.line((500 + 6 * side * run.foot, 150 + 8 * (side > 0)),
                      up(80, 10 * side), 9, (40, 44, 70), self.g())
        self.poly([up(80, -24), up(80, 24), up(165, 28), up(165, -28)],
                  (200, 60, 70), self.g())
        self.disc(up(190), 20, (236, 200, 170), self.g())
        self.poly([up(203, -22), up(203, 22), up(214, 14), up(214, -14)],
                  (30, 30, 40), self.g())
        mid = 500 + model.REACH * run.pole() * 0.35
        tilt = math.tan(lean) * 0.5

        def pole(x: float):
            return (x, 250.0 - (x - 500.0) * tilt)
        self.line(pole(mid - 0.75 * model.REACH),
                  pole(mid + 0.75 * model.REACH), 7, (236, 226, 190),
                  self.g())
        for side in (-1, 1):
            self.line(up(150, 24 * side), pole(500 + 60 * side), 8,
                      (200, 60, 70), self.g())
            self.disc(pole(500 + 60 * side), 8, (236, 200, 170), self.g())
        for end in run.perched:
            bx, by = run.bird_spot(end)
            self.oval((bx, by + 12), 16, 11, (40, 40, 50), self.g())
            self.disc((bx + 9 * end, by + 22), 7, (40, 40, 50), self.g())
            self.poly([(bx + 15 * end, by + 23), (bx + 24 * end, by + 20),
                       (bx + 15 * end, by + 18)], (250, 180, 60), self.g())
        hud = pyglet.graphics.Group(order=900)
        self.rect(250, 606, 500, 10, (20, 24, 40, 220), hud)
        self.rect(250, 606, 500 * share, 10, (110, 220, 140), hud)
        self.words(_('%d of %d steps') % (run.taken, level.steps), 500, 588,
                   12, group=hud, colour=(255, 255, 255, 230))
        danger = abs(lean) / model.FALL
        if danger > 0.5:
            self.words(_('LEANING'), 500, 560, 14, bold=True, group=hud,
                       colour=(255, 120, 90, 255))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d steps') % (
            self.rung, self.trial, self.total_trials, run.level.steps)
