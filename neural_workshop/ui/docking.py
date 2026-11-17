# -*- coding: utf-8 -*-
"""Docking on screen: the view from the cockpit.

Ahead, the station's face and its port: a ring, and in the middle a
cross on a post standing out from the face. Lined up, the cross sits in
the middle of the ring; off the line, it sits off toward the way to
go. On the low rungs range and closing speed are shown; the fuel left
always is.

WASD push across and up, R / F forward and back; the arrows turn the
nose; Q / E roll.

For the agent boundary: ports 0-5 push left, right, down, up, forward,
back; 6-11 turn left, right, down, up and roll left, right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Optional

from pyglet.window import key

from .. import docking as model
from ..i18n import _
from .lens import Lens
from .livetask import LiveTask

STARS = [(random.Random(k).uniform(-1, 1), random.Random(k + 999).uniform(-1, 1),
          random.Random(k + 7).uniform(0.2, 1)) for k in range(160)]


class Docking(LiveTask):
    """Dock square, centred and slow."""

    instance: Optional['Docking'] = None

    TITLE = 'Docking'
    TASK_ID = 'docking'
    PREFIX = 'BERTH'
    CATEGORY = 'planning'
    MODEL = model
    BACK = (4, 6, 14)
    FOOTNOTE = _('WASD: across / up   R / F: forward / back   '
                 'Arrows: nose   Q / E: roll   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Dock: centred, square and slow')
        return ok

    def _held(self):
        k = self.keys
        for keys, port in (((key.A,), model.LEFT), ((key.D,), model.RIGHT),
                           ((key.S,), model.DOWN), ((key.W,), model.UP),
                           ((key.R,), model.FORE), ((key.F,), model.AFT),
                           ((key.LEFT,), model.YAW_L),
                           ((key.RIGHT,), model.YAW_R),
                           ((key.DOWN,), model.PITCH_D),
                           ((key.UP,), model.PITCH_U),
                           ((key.Q,), model.ROLL_L), ((key.E,), model.ROLL_R)):
            if any(k[s] for s in keys):
                return port
        return None

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height)
        att = run.att
        eye = tuple(run.pos)
        fwd = model.body_to_world((0, 0, 1), *att)
        up = model.body_to_world((0, 1, 0), *att)
        focal = width / (2 * math.tan(math.radians(30)))
        lens = Lens(eye, tuple(e + f for e, f in zip(eye, fwd)), focal,
                    left + width / 2, bottom + height / 2, up=up,
                    x_right=True)
        g = self.layer()
        for sx, sy, b in STARS:
            p = lens.see((eye[0] + 400 * sx, eye[1] + 400 * sy, eye[2] + 400))
            if p and left < p[0] < left + width and \
                    bottom < p[1] < bottom + height:
                c = int(120 + 120 * b)
                self.disc(p, 1.2, (c, c, c), g)
        roll = run.station_roll()

        def turned(x, y, z):
            c, s = math.cos(roll), math.sin(roll)
            return (x * c - y * s, x * s + y * c, z)

        g = self.layer()
        n = 40
        self.face(lens, [turned(7 * math.cos(2 * math.pi * k / n),
                                7 * math.sin(2 * math.pi * k / n), 0.0)
                         for k in range(n)], (120, 124, 136), g)
        for k in range(8):
            a = 2 * math.pi * k / 8
            self.seg(lens, turned(1.4 * math.cos(a), 1.4 * math.sin(a), -0.01),
                     turned(7 * math.cos(a), 7 * math.sin(a), -0.01), 2,
                     (90, 94, 106), g)
        g = self.layer()
        ring = [turned(0.9 * math.cos(2 * math.pi * k / 32),
                       0.9 * math.sin(2 * math.pi * k / 32), -0.02)
                for k in range(32)]
        self.face(lens, ring, (40, 44, 56), g)
        for a, b in zip(ring, ring[1:] + ring[:1]):
            self.seg(lens, a, b, 3, (250, 200, 80), g)
        g = self.layer()
        self.seg(lens, turned(0, 0, -0.02), turned(0, 0, -1.0), 3,
                 (220, 220, 230), g)
        for a, b in (((-0.35, 0), (0.35, 0)), ((0, -0.35), (0, 0.35))):
            self.seg(lens, turned(a[0], a[1], -1.0), turned(b[0], b[1], -1.0),
                     3, (250, 250, 255), g)
        # the cockpit's own sight
        cx, cy = left + width / 2, bottom + height / 2
        g = self.layer()
        for dx, dy in ((-30, 0), (30, 0), (0, -30), (0, 30)):
            self.line((cx + dx * 0.4, cy + dy * 0.4), (cx + dx, cy + dy), 2,
                      (110, 240, 140, 200), g)
        fuel = max(0.0, run.fuel / max(1e-6, run.ap.fuel))
        self.rect(left + 16, bottom + 16, 16, (height - 32) * fuel,
                  (110, 200, 140) if fuel > 0.25 else (230, 110, 80), g)
        if run.level.readouts:
            rng = math.sqrt(sum(p * p for p in run.pos))
            self.say(_('range %.1f m   closing %.2f m/s (at most %.2f)') % (
                rng, run.vel[2], run.level.vmax), left + width / 2,
                bottom + 24, 12, (180, 240, 190, 255))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   fuel %.0f s') % (
            self.rung, self.trial, self.total_trials, max(0.0, self.run.fuel))
