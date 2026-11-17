# -*- coding: utf-8 -*-
"""Free Kick on screen: from behind the ball, toward the goal.

The lit ring hangs in the goal mouth; on the low rungs a dotted line
shows where the kick as set would go. The dials along the bottom show
the kick's direction, height, curl and power. A flag by the goal shows
the wind.

Left / Right aim, Up / Down height, A / D curl, W / S power, Space kicks.

For the agent boundary: ports 0-7 aim left, right, raise, lower, curl
left, right, harder, softer; port 8 kicks.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key

from .. import freekick as model
from ..i18n import _
from .livetask import LiveTask


class FreeKick(LiveTask):
    """Curl it into the ring."""

    instance: Optional['FreeKick'] = None

    TITLE = 'Free Kick'
    TASK_ID = 'free_kick'
    PREFIX = 'KICK'
    CATEGORY = 'attention'
    MODEL = model
    BACK = (30, 70, 40)
    EVENT_KEYS = {key.SPACE: model.KICK}
    FOOTNOTE = _('Left / Right: aim   Up / Down: height   A / D: curl   '
                 'W / S: power   Space: kick   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Kick it into the lit ring')
        return ok

    def _held(self):
        k = self.keys
        for keys, port in (((key.LEFT,), model.AIM_L),
                           ((key.RIGHT,), model.AIM_R),
                           ((key.UP,), model.RAISE), ((key.DOWN,), model.LOWER),
                           ((key.A,), model.CURL_L), ((key.D,), model.CURL_R),
                           ((key.W,), model.HARDER),
                           ((key.S,), model.SOFTER)):
            if any(k[s] for s in keys):
                return port
        return None

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        p = run.p
        self.frame(left, bottom, width, height, (120, 170, 220))
        sx, sz = p.spot
        eye = (sx * 0.85, 2.4, sz + 7.0)
        aim = (p.goal_x * 0.5 + sx * 0.5, 0.0, sz * 0.45)
        look = tuple(t - e for t, e in zip(aim, eye))
        lens = self.camera(eye, look, left, bottom + 40, width, height - 40,
                           52)
        g = self.layer()
        # the grass, in stripes, far to near
        for k in range(-2, 16):
            z0, z1 = k * 2.5, (k + 1) * 2.5
            self.face(lens, [(-30, 0, z0), (30, 0, z0), (30, 0, z1),
                             (-30, 0, z1)],
                      (70, 150, 70) if k % 2 else (62, 138, 62), g)
        g = self.layer()
        for a, b in (((-20.16, 0.01, 0), (20.16, 0.01, 0)),
                     ((-20.16, 0.01, 0), (-20.16, 0.01, 16.5)),
                     ((20.16, 0.01, 0), (20.16, 0.01, 16.5)),
                     ((-20.16, 0.01, 16.5), (20.16, 0.01, 16.5)),
                     ((-9.16, 0.01, 0), (-9.16, 0.01, 5.5)),
                     ((9.16, 0.01, 0), (9.16, 0.01, 5.5)),
                     ((-9.16, 0.01, 5.5), (9.16, 0.01, 5.5))):
            self.seg(lens, a, b, 2, (230, 240, 230), g)
        # the net and the goal
        gx = p.goal_x
        w2, hh = model.WIDE / 2, model.HIGH
        g = self.layer()
        self.face(lens, [(gx - w2, 0, -2), (gx + w2, 0, -2),
                         (gx + w2, hh, -1.2), (gx - w2, hh, -1.2)],
                  (200, 205, 210), g)
        for k in range(0, 15):
            x = gx - w2 + k * model.WIDE / 14
            self.seg(lens, (x, 0, -2), (x, hh, -1.2), 1, (170, 175, 180), g)
        rx, ry, rr = p.ring
        self.face(lens, [(rx + rr * math.cos(a), ry + rr * math.sin(a), -0.02)
                         for a in (k * math.pi / 16 for k in range(32))],
                  (255, 230, 90), g)
        g = self.layer()
        for a, b in (((gx - w2, 0, 0), (gx - w2, hh, 0)),
                     ((gx + w2, 0, 0), (gx + w2, hh, 0)),
                     ((gx - w2, hh, 0), (gx + w2, hh, 0))):
            self.seg(lens, a, b, 5, (250, 250, 250), g)
        # the keeper
        if p.level.keeper:
            kx = run.keeper_x()
            self.box(lens, kx - 0.3, 0.0, -0.3, kx + 0.3, 1.6, 0.0,
                     (60, 60, 70), g)
            self.ball(lens, (kx, 1.8, -0.15), 0.14, (230, 190, 160), g)
            self.seg(lens, (kx - 0.3, 1.35, -0.1), (kx - 0.9, 1.9, -0.1), 4,
                     (240, 120, 40), g)
            self.seg(lens, (kx + 0.3, 1.35, -0.1), (kx + 0.9, 1.9, -0.1), 4,
                     (240, 120, 40), g)
        # the wall
        if p.level.wall:
            wx, wz, ww, wh = p.wall
            up = p.level.jump if run.kicked is not None and \
                run.t - run.kicked < 0.8 else 0.0
            g = self.layer()
            n = p.level.wall
            for k in range(n):
                x0 = wx - ww + k * 2 * ww / n
                self.box(lens, x0 + 0.03, up, wz - 0.25, x0 + 2 * ww / n - 0.03,
                         up + 1.65, wz, (200, 40, 50), g)
                self.ball(lens, (x0 + ww / n, up + 1.8, wz - 0.12), 0.13,
                          (230, 190, 160), g)
        # the wind's flag by the corner of the goal
        if p.level.wind:
            fx, fz = gx + w2 + 3.0, 0.0
            g = self.layer()
            self.seg(lens, (fx, 0, fz), (fx, 3.2, fz), 2, (240, 240, 240), g)
            wx, wz = p.wind
            s = math.hypot(wx, wz)
            ux, uz = wx / s, wz / s
            n = 0.25 + 0.2 * s
            self.face(lens, [(fx, 3.2, fz), (fx + ux * n, 3.0, fz + uz * n),
                             (fx, 2.8, fz)], (240, 70, 60), g)
        # the flight, drawn on the low rungs
        if p.level.guide and run.kicked is None:
            path = model.fly(p, run.kick, keep=True)[2]
            g = self.layer()
            for t, x, y, z in path[::6]:
                self.ball(lens, (x, y, z), 0.05, (255, 255, 255), g, 0.0)
        g = self.layer()
        bx, by, bz = run.ball()
        self.ball(lens, (bx, 0.01, bz), 0.1, (40, 90, 40), g, 0.0)
        self.ball(lens, (bx, by, bz), model.BALL, (250, 250, 250), g)
        self._dials(run, left, bottom, width)

    def _dials(self, run, left, bottom, width) -> None:
        g = self.layer()
        k = run.kick
        items = ((_('aim'), k.aim, model.LIMITS['aim']),
                 (_('height'), k.lift, model.LIMITS['lift']),
                 (_('curl'), -k.curl, (model.LIMITS['curl'][0],
                                        model.LIMITS['curl'][1])),
                 (_('power'), k.power, model.LIMITS['power']))
        w = (width - 60) / 4
        for i, (name, v, (lo, hi)) in enumerate(items):
            x = left + 20 + i * (w + 7)
            self.rect(x, bottom + 8, w, 12, (20, 40, 25), g)
            u = (v - lo) / (hi - lo)
            self.rect(x + w * u - 3, bottom + 5, 6, 18, (250, 230, 120), g)
            self.say(name, x + w / 2, bottom + 32, 11, (230, 245, 230, 255))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
