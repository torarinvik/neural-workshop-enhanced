# -*- coding: utf-8 -*-
"""Glove on screen: the pitch, seen from wherever the camera has cut to.

Move the mouse -- or the arrow keys -- and the glove moves the way the
screen shows: right on the screen is right in the picture, whichever
angle the picture now has.

For the agent boundary: ports 0-3 move the glove up, down, left, right
on the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key

from .. import glove as model
from ..i18n import _
from .livetask import LiveTask


class Glove(LiveTask):
    """Catch every pitch."""

    instance: Optional['Glove'] = None

    TITLE = 'Glove'
    TASK_ID = 'glove'
    PREFIX = 'GLOVE'
    CATEGORY = 'attention'
    MODEL = model
    BACK = (60, 110, 60)
    FOOTNOTE = _('Mouse or arrows: move the glove   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Catch the pitches')
        self._lens = None
        return ok

    def _held(self):
        k = self.keys
        for keys, port in (((key.UP, key.W), model.UP),
                           ((key.DOWN, key.S), model.DOWN),
                           ((key.LEFT, key.A), model.LEFT),
                           ((key.RIGHT, key.D), model.RIGHT)):
            if any(k[s] for s in keys):
                return port
        return None

    def on_mouse_motion(self, x, y, dx, dy):
        super().on_mouse_motion(x, y, dx, dy)
        self._mouse(dx, dy)

    def _drag(self, dx, dy, buttons, modifiers) -> None:
        self._mouse(dx, dy)

    def _mouse(self, dx, dy) -> None:
        run, lens = self.run, getattr(self, '_lens', None)
        if run is None or lens is None or self.phase != self.PLAY or \
                run.result is not None:
            return
        q = lens.see((run.glove[0], run.glove[1], 0.0))
        if q is None:
            return
        # the plane's move that carries the glove's picture by (dx, dy)
        e = 0.01
        gx, gy = run.glove
        px = lens.see((gx + e, gy, 0.0))
        py = lens.see((gx, gy + e, 0.0))
        if px is None or py is None:
            return
        a, b = (px[0] - q[0]) / e, (py[0] - q[0]) / e
        c, d = (px[1] - q[1]) / e, (py[1] - q[1]) / e
        det = a * d - b * c
        if abs(det) < 1e-6:
            return
        mx, my = (d * dx - b * dy) / det, (a * dy - c * dx) / det
        # a view that barely sees a direction must not fling the glove
        cap = 0.25
        n = math.hypot(mx, my)
        if n > cap:
            mx, my = mx * cap / n, my * cap / n
        run.move(mx, my)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height, (140, 190, 230))
        eye, look = model.VIEWS[run.view()]
        lens = self.camera(eye, tuple(l - e for l, e in zip(look, eye)),
                           left, bottom, width, height, 76)
        self._lens = lens
        g = self.layer()
        self.face(lens, [(-40, 0, -30), (40, 0, -30), (40, 0, 60),
                         (-40, 0, 60)], (70, 140, 70), g)
        self.face(lens, [(-14, 0.002, -4), (14, 0.002, -4), (14, 0.002, 24),
                         (-14, 0.002, 24)], (176, 132, 90), g)
        g = self.layer()
        self.face(lens, [(2.7 * math.cos(a), 0.004, model.MOUND + 0.4 +
                          2.7 * math.sin(a))
                         for a in (k * math.pi / 12 for k in range(24))],
                  (190, 146, 100), g)
        self.face(lens, [(-0.22, 0.006, 0.0), (0.22, 0.006, 0.0),
                         (0.22, 0.006, -0.22), (0.0, 0.006, -0.43),
                         (-0.22, 0.006, -0.22)], (250, 250, 250), g)
        # the pitcher
        g = self.layer()
        mx, mz = model.RELEASE[0], model.MOUND + 0.5
        self.box(lens, mx - 0.25, 0, mz - 0.15, mx + 0.25, 1.5, mz + 0.15,
                 (40, 60, 150), g)
        self.ball(lens, (mx, 1.7, mz), 0.13, (230, 190, 160), g)
        # the catcher behind the plate, crouched -- not in the view
        # from behind the catcher, which is theirs
        if run.view() != 0:
            self._catcher(lens, g)
        # the glove on the plate's plane, and the ball, nearer first last
        r = run.level.glove
        gx, gy = run.glove
        glove = [(gx + r * math.cos(a), gy + r * math.sin(a), 0.0)
                 for a in (k * math.pi / 12 for k in range(24))]
        b = run.ball()
        items = [(math.dist(eye, (gx, gy, 0.0)), 'glove', None)]
        if b is not None:
            items.append((math.dist(eye, b), 'ball', b))
        g = self.layer()
        if b is not None:
            self.ball(lens, (b[0], 0.01, b[2]), 0.05, (50, 90, 50), g, 0.0)
        for _d, kind, it in sorted(items, key=lambda i: -i[0]):
            if kind == 'glove':
                # see-through, so the ball shows through it as it comes
                colour = (225, 160, 80, 150)
                if run.flash and run.t - run.flash[0] < 0.4:
                    colour = (90, 220, 110, 200) if run.flash[1] else \
                        (230, 80, 70, 200)
                self.face(lens, glove, colour, g)
                for a, b in zip(glove, glove[1:] + glove[:1]):
                    self.seg(lens, a, b, 3, (90, 45, 15), g)
                self.face(lens, [(gx + 0.45 * r * math.cos(a),
                                  gy + 0.45 * r * math.sin(a), -0.01)
                                 for a in (k * math.pi / 8
                                           for k in range(16))],
                          (110, 60, 25, 150), g)
            else:
                self.ball(lens, it, 0.075, (250, 250, 245), g)
        g = self.layer()
        self.say(_('caught %d   missed %d') % (run.caught, run.missed),
                 left + width / 2, bottom + 18, 13, (255, 255, 255, 255),
                 group=None)

    def _catcher(self, lens, g) -> None:
        self.box(lens, -0.3, 0, -1.0, 0.3, 0.95, -0.55, (60, 60, 70), g)
        self.ball(lens, (0.0, 1.1, -0.75), 0.15, (40, 40, 50), g)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   pitch %d of %d') % (
            self.rung, self.trial, self.total_trials,
            min(len(self.run.g.pitches), self.run.next + 1),
            len(self.run.g.pitches))
