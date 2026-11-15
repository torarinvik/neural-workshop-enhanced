# -*- coding: utf-8 -*-
"""Gunslinger on screen: the notice along the top, the street under it.

A street running away between two rows of buildings under a hot sky.
The men stand in it in long coats and coloured hats; a man's arm hangs
at his side, twitches when he feints, and comes up level when he draws.
Your holster is at the bottom right with the gun's grip showing; once
the gun is in your hand a sight follows the pointer (and wanders, on
the higher rungs) and the cylinder at the bottom left shows the rounds
left and whether the hammer is back. There is no clock on the screen:
when he will draw is the thing not known.

Mouse: drag the gun up out of the holster and let go; click to shoot.
Keys: Space cocks the hammer.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; port 14 cocks the hammer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import gunslinger as model
from ..i18n import _
from . import polish
from .handtask import HandTask

HAT = ((204, 52, 44), (24, 24, 28), (240, 238, 228), (52, 140, 70),
       (120, 78, 40), (60, 100, 200))
COATS = ((70, 60, 56), (90, 74, 58), (58, 62, 74), (84, 60, 60))


class Gunslinger(HandTask):
    """Draw when he draws, and be the quicker."""

    instance: Optional['Gunslinger'] = None

    TITLE = 'Gunslinger'
    TASK_ID = 'gunslinger'
    PREFIX = 'GUN'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.SPACE: model.COCK}
    BACK = (60, 44, 36)
    TIME_BAR = False
    FOOTNOTE = _('Drag the gun up out of the holster, let go, click to '
                 'shoot   Space: cock the hammer   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Wait for him. Do not touch your gun first')
        return ok

    def _scene(self, run, s: float) -> None:
        view = run.view()
        see = view.see
        G = pyglet.graphics.Group
        layer = [0]

        def g():
            layer[0] += 1
            return G(order=layer[0])

        ox, oy, k = self.fit
        far = see((0.0, 0.0, -400.0))
        horizon = far[1] if far else 300.0
        polish.gradient(self.drawn, self.batch, ox, oy + horizon * k,
                        1000 * k, (640 - horizon) * k, (250, 214, 150),
                        (120, 170, 220), bands=14, group=G(order=-5))
        self.rect(0, 0, 1000, horizon, (206, 170, 112), G(order=-4))
        for side in (-1, 1):
            for n in range(5):
                z0, z1 = -5.0 - 6.5 * n, -10.5 - 6.5 * n
                tall = 4.0 + 1.3 * ((n * 7 + (3 if side > 0 else 0)) % 3)
                x = side * 7.0
                wall = [see((x, 0, z0)), see((x, 0, z1)), see((x, tall, z1)),
                        see((x, tall, z0))]
                shade = (150 - 12 * n, 104 - 8 * n, 70 - 5 * n)
                self.poly(wall, shade, G(order=-3))
                end = [see((x, 0, z0)), see((x + side * 4, 0, z0)),
                       see((x + side * 4, tall, z0)), see((x, tall, z0))]
                self.poly(end, polish.mix(shade, (0, 0, 0), 0.25),
                          G(order=-2))
        men = sorted(range(len(run.duel.men)),
                     key=lambda j: -run.duel.men[j].z)
        for j in men:
            self._man(run, j, view, g)
        thick = run.dust()
        top = G(order=800)
        if thick > 0.01:
            self.rect(0, 0, 1000, 560, (214, 184, 132, int(255 * thick)),
                      top)
        hud, text = G(order=900), G(order=901)
        for t, x, y in run.shots:
            if run.t - t < 0.12:
                self.disc((x, y), 16, (255, 240, 180, 200), hud)
        # The holster, the gun and the sight.
        hx, hy = model.HOLSTER
        self.poly([(hx - 34, hy - 70), (hx + 34, hy - 70), (hx + 26, hy + 20),
                   (hx - 26, hy + 20)], (96, 60, 34), hud)
        if run.gun == 'holster':
            self.poly([(hx - 14, hy + 10), (hx + 14, hy + 10),
                       (hx + 20, hy + 52), (hx - 8, hy + 52)],
                      (40, 36, 36), text)
        elif run.gun == 'pulling':
            px, py = run.hand.x, run.hand.y
            self.poly([(px - 14, py - 40), (px + 14, py - 40),
                       (px + 20, py + 6), (px - 8, py + 6)], (40, 36, 36),
                      text)
        else:
            ax, ay = run.aim()
            self.poly([(ax + 150, 0), (ax + 196, 0), (ax + 40, ay - 60),
                       (ax + 24, ay - 46)], (40, 36, 36), hud)
            for a, b in (((ax - 16, ay), (ax - 5, ay)),
                         ((ax + 5, ay), (ax + 16, ay)),
                         ((ax, ay - 16), (ax, ay - 5)),
                         ((ax, ay + 5), (ax, ay + 16))):
                self.line(a, b, 2.5, (255, 255, 255, 235), text)
        for n in range(model.BULLETS):
            a = 2 * math.pi * n / model.BULLETS
            self.disc((70 + 22 * math.cos(a), 70 + 22 * math.sin(a)), 7,
                      (230, 190, 90) if n < run.bullets else (60, 50, 44),
                      text)
        if run.level.cock:
            self.words(_('COCKED') if run.cocked else _('Space: cock'), 70,
                       24, 11, bold=True, group=text,
                       colour=(140, 240, 160, 255) if run.cocked
                       else (255, 220, 160, 255))
        self.rect(20, 580, 960, 48, (30, 20, 14, 225), hud)
        self.words(run.duel.notice, 500, 604, 17, bold=True, group=text,
                   colour=(255, 240, 210, 255))
        if run.level.word and run.drawn() and run.result is None:
            self.words(_('DRAW!'), 500, 500, 44, bold=True, group=text,
                       colour=(255, 60, 40, 255))

    def _man(self, run, j, view, g) -> None:
        see = view.see
        x, _y, z = run.stands(j)
        feet = see((x, 0.0, z))
        if feet is None:
            return
        u = view.size(1.0, feet[2])                  # a metre, in units
        cx, by = feet[0], feet[1]
        coat = COATS[j % len(COATS)]
        if run.fell == j:
            self.rect(cx - 0.9 * u, by, 1.8 * u, 0.3 * u, coat, g())
            return
        for side in (-1, 1):
            self.rect(cx + side * 0.16 * u - 0.09 * u, by, 0.18 * u,
                      0.9 * u, (40, 34, 34), g())
        self.rect(cx - 0.3 * u, by + 0.8 * u, 0.6 * u, 0.75 * u, coat, g())
        self.disc((cx, by + 1.7 * u), 0.15 * u, (226, 186, 150), g())
        if j not in run.hatless:
            hat = HAT[run.duel.men[j].hat]
            self.rect(cx - 0.32 * u, by + 1.83 * u, 0.64 * u, 0.06 * u, hat,
                      g())
            self.rect(cx - 0.19 * u, by + 1.87 * u, 0.38 * u, 0.24 * u, hat,
                      g())
        # His gun arm: hanging, reaching, or up and level.
        arm = run.arm(j)
        sx, sy = cx + 0.3 * u, by + 1.45 * u
        a = -math.pi / 2 + arm * (math.pi / 2 + 0.2)
        ex, ey = sx + 0.55 * u * math.cos(a) * (0.4 + 0.6 * arm), \
            sy + 0.55 * u * math.sin(a)
        self.line((sx, sy), (ex, ey), max(2.0, 0.12 * u), coat, g())
        if arm > 0.75:
            self.disc((ex, ey), max(2.5, 0.09 * u), (20, 20, 22), g())
        else:
            self.rect(cx + 0.27 * u, by + 0.75 * u, 0.1 * u, 0.22 * u,
                      (60, 40, 26), g())

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d rounds') % (
            self.rung, self.trial, self.total_trials, run.bullets)
