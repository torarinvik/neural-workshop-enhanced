# -*- coding: utf-8 -*-
"""Unicycle on screen: side on, the camera following the rider.

Up / W pedals, Down / S back-pedals, Left / A leans back, Right / D
leans forward; pedal and lean together by holding both.

For the agent boundary: ports 0-1 pedal and back-pedal, 2-3 lean back
and forward, 4-7 pedal or back-pedal while leaning back or forward.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key

from .. import unicycle as model
from ..i18n import _
from .livetask import LiveTask

SCALE = 70.0                   # pixels a metre


class Unicycle(LiveTask):
    """Ride to the flag on one wheel."""

    instance: Optional['Unicycle'] = None

    TITLE = 'Unicycle'
    TASK_ID = 'unicycle'
    PREFIX = 'UNI'
    CATEGORY = 'planning'
    MODEL = model
    BACK = (150, 200, 235)
    FOOTNOTE = _('Up / Down: pedal / back-pedal   Left / Right: lean back '
                 '/ forward   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Ride to the flag. Keep your head off the ground')
        return ok

    def _held(self):
        k = self.keys
        drive = (1 if k[key.UP] or k[key.W] else 0) - \
            (1 if k[key.DOWN] or k[key.S] else 0)
        lean = (1 if k[key.RIGHT] or k[key.D] else 0) - \
            (1 if k[key.LEFT] or k[key.A] else 0)
        table = {(0, 0): None, (1, 0): model.PEDAL, (-1, 0): model.BACK,
                 (0, -1): model.LEAN_B, (0, 1): model.LEAN_F,
                 (1, -1): model.PEDAL_B, (1, 1): model.PEDAL_F,
                 (-1, -1): model.BACK_B, (-1, 1): model.BACK_F}
        return table[(drive, lean)]

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        tr, b = run.tr, run.body
        self.frame(left, bottom, width, height)
        cx = b.px + 1.5
        cy = (b.py + model.ground(tr, b.px)) / 2 + 0.8
        ox, oy = left + width / 2, bottom + height / 2

        def at(x, y):
            return (ox + (x - cx) * SCALE, oy + (y - cy) * SCALE)

        # far hills for the sense of motion
        g = self.layer()
        for k in range(-2, 8):
            hx = (k * 9.0 - cx * 0.3) % 90.0 - 20.0
            base = left + (hx / 70.0) * width
            self.poly([(base, bottom), (base + 160, bottom + height * 0.55),
                       (base + 320, bottom)], (175, 210, 225), g)
        # the ground
        g = self.layer()
        half = width / 2 / SCALE + 1
        x = cx - half
        while x < cx + half:
            x1 = x + model.DX
            a, c = at(x, model.ground(tr, x)), at(x1, model.ground(tr, x1))
            self.poly([(a[0], bottom), (a[0], a[1]), (c[0], c[1]),
                       (c[0], bottom)], (110, 84, 60), g)
            self.line(a, c, 5, (90, 160, 70), g)
            x = x1
        # the flag
        fy = model.ground(tr, tr.finish)
        self.line(at(tr.finish, fy), at(tr.finish, fy + 2.4), 3,
                  (240, 240, 240), g)
        self.poly([at(tr.finish, fy + 2.4), at(tr.finish + 0.9, fy + 2.1),
                   at(tr.finish, fy + 1.8)], (230, 60, 60), g)
        # the wheel and its spokes
        g = self.layer()
        w = at(b.px, b.py)
        self.disc(w, model.R * SCALE, (40, 40, 46), g)
        self.disc(w, model.R * SCALE - 6, (200, 205, 215), g)
        for k in range(6):
            t = b.a + k * math.pi / 3
            self.line(w, (w[0] + math.cos(t) * (model.R * SCALE - 6),
                          w[1] + math.sin(t) * (model.R * SCALE - 6)), 2,
                      (90, 90, 100), g)
        # the rider: seat at the body's point, head beyond it
        seat = at(b.qx, b.qy)
        hx, hy = model.head(b)
        top = at(b.px + (b.qx - b.px) * 1.32, b.py + (b.qy - b.py) * 1.32)
        g = self.layer()
        self.line(w, seat, 4, (60, 60, 70), g)
        for k in (0, math.pi):
            t = b.a + k
            pedal = (w[0] + math.cos(t) * 0.16 * SCALE,
                     w[1] + math.sin(t) * 0.16 * SCALE)
            knee = ((seat[0] + pedal[0]) / 2 + 0.22 * SCALE,
                    (seat[1] + pedal[1]) / 2 + 0.05 * SCALE)
            self.line(seat, knee, 7, (40, 60, 140), g)
            self.line(knee, pedal, 6, (40, 60, 140), g)
        self.line(seat, top, 12, (220, 90, 60), g)
        arm = ((seat[0] + top[0]) / 2, (seat[1] + top[1]) / 2)
        self.line(top, (arm[0] + 0.35 * SCALE, arm[1]), 5, (220, 90, 60), g)
        self.disc(at(hx, hy), 0.17 * SCALE, (240, 200, 170), g)
        # how far, and the time left
        g = self.layer()
        u = max(0.0, min(1.0, b.px / tr.finish))
        self.rect(left + 20, bottom + height - 22, (width - 40), 6,
                  (60, 70, 90), g)
        self.rect(left + 20, bottom + height - 22, (width - 40) * u, 6,
                  (250, 220, 90), g)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   %.0f s left') % (
            self.rung, self.trial, self.total_trials,
            max(0.0, self.run.tr.seconds - self.run.t))
