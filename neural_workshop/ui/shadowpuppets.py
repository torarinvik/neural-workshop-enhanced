# -*- coding: utf-8 -*-
"""Shadow Puppets on screen: the figure, the lamp and the wall.

The figure of blocks turns in front of you; behind it the lamp throws
its shadow on the wall. The shadow wanted is drawn pale on the wall
under the real one, or on a card in the corner, or only named, by
rung; on the high rungs a screen hides the figure and the shadow is
all there is. A bar fills while the shadow holds.

Mouse: drag to turn the figure. Keys: Q and E roll it.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 and 15 roll the figure a little left and
right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import shadowpuppets as model
from ..i18n import _
from . import polish
from .handtask import HandTask

FACES = (((1, 0, 0), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))),
         ((-1, 0, 0), ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1))),
         ((0, 1, 0), ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1))),
         ((0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
         ((0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
         ((0, 0, -1), ((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1))))
WALL = (236, 222, 186)
LIGHT = (0.4, 0.6, 0.7)


class ShadowPuppets(HandTask):
    """Turn the figure until its shadow is the one asked for."""

    instance: Optional['ShadowPuppets'] = None

    TITLE = 'Shadow Puppets'
    TASK_ID = 'shadow_puppets'
    PREFIX = 'PUPPET'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    BACK = (24, 20, 28)
    FOOTNOTE = _('Drag: turn the figure   Q / E: roll it   Hold the shadow '
                 'on the shape   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        self.message = (_('Cast the shadow of a %s') % run.name()
                        if run.level.shown == 'named'
                        else _('Cast the shadow shown'))
        return ok

    def _held(self):
        k = self.keys
        if k[key.Q]:
            self.steer(model.ROLL_LEFT)
        elif k[key.E]:
            self.steer(model.ROLL_RIGHT)
        return None

    def _cells(self, cells, cx, cy, size, colour, group) -> None:
        for x, y in cells:
            self.rect(cx + (x - 0.5) * size, cy + (y - 0.5) * size, size,
                      size, colour, group)

    def _scene(self, run, s: float) -> None:
        m, level = model, run.level
        self.rect(0, 0, 1000, 640, (34, 28, 36), self.g())
        self.oval((500, 400), 330, 230, polish.mix((34, 28, 36), WALL, 0.55),
                  self.g(), 32)
        self.oval((500, 400), 290, 200, WALL, self.g(), 32)
        self.rect(0, 0, 1000, 150, (60, 44, 40), self.g())  # the table
        cx, cy, size = 500.0, 400.0, 62.0
        if level.shown == 'wall':
            self._cells(run.wanted(), cx, cy, size, (150, 190, 230),
                        self.g())
        shade = self.g()
        cubes = set(run.cubes)
        faces = []
        for c in run.cubes:
            for normal, corners in FACES:
                if tuple(c[i] + normal[i] for i in range(3)) in cubes:
                    continue
                pts = [m.put(run.m, tuple(c[i] + 0.5 * q[i]
                                           for i in range(3)))
                       for q in corners]
                self.poly([(cx + p[0] * size, cy + p[1] * size)
                           for p in pts], (56, 50, 66), shade)
                n = m.put(run.m, normal)
                if n[2] > 0.02:
                    faces.append((sum(p[2] for p in pts), n, pts))
        if level.hidden:
            self.rect(300, 0, 400, 240, (90, 40, 50), self.g())
            for k in range(8):
                self.rect(300 + 50 * k, 0, 4, 240, (70, 30, 40), self.g())
            self.words(_('the figure is behind the screen'), 500, 120, 13,
                       group=self.g(), colour=(250, 230, 220, 255))
        else:
            fx, fy, fs = 500.0, 112.0, 36.0
            faces.sort(key=lambda f: f[0])
            for _z, n, pts in faces:
                lit = 0.35 + 0.65 * max(0.0, sum(n[i] * LIGHT[i]
                                                 for i in range(3)))
                self.poly([(fx + p[0] * fs, fy + p[1] * fs) for p in pts],
                          polish.mix((0, 0, 0), (230, 150, 80), lit),
                          self.g())
        self.disc((500, 20), 16, (255, 240, 170), self.g())  # the lamp
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        if level.shown == 'card':
            self.rect(800, 440, 170, 170, (250, 246, 236), hud)
            self._cells(run.wanted(), 885, 525, 44, (40, 34, 50), text)
        elif level.shown == 'named':
            self.rect(330, 596, 340, 34, (16, 14, 20, 225), hud)
            self.words(_('Cast a %s') % run.name(), 500, 613, 16, bold=True,
                       group=text, colour=(255, 255, 255, 255))
        self.words(_('shadow %d of %d') % (min(run.at + 1, len(run.fits)),
                                           len(run.fits)), 90, 610, 12,
                   group=text, colour=(230, 230, 230, 255))
        self.rect(40, 584, 100, 8, (60, 50, 60), hud)
        self.rect(40, 584, 100 * min(1.0, run.stay / m.STAY), 8,
                  (110, 220, 140), text)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d shadows') % (
            self.rung, self.trial, self.total_trials, run.level.shadows)
