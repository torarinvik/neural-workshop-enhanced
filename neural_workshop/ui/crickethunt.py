# -*- coding: utf-8 -*-
"""Cricket Hunt on screen: a dark room from inside it.

W / S or Up / Down walk, A / D or Left / Right turn, Q / E look up and
down (or drag the mouse to look); Space grabs at what you are looking
at. The crickets are not drawn until caught.

For the agent boundary: ports 0-5 walk forward / back, turn left /
right, look up / down; port 6 grabs.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key, mouse

from .. import crickethunt as model
from ..i18n import _
from .livetask import LiveTask


class CricketHunt(LiveTask):
    """Find the crickets by ear."""

    instance: Optional['CricketHunt'] = None

    TITLE = 'Cricket Hunt'
    TASK_ID = 'cricket_hunt'
    PREFIX = 'CRICKET'
    CATEGORY = 'perception'
    MODEL = model
    BACK = (8, 9, 14)
    EVENT_KEYS = {key.SPACE: model.GRAB}
    FOOTNOTE = _('W/S walk  A/D turn  Q/E or drag: look up/down  '
                 'Space: grab   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Find the crickets by their chirping')
        return ok

    def _held(self):
        k = self.keys
        for keys, port in (((key.W, key.UP), model.FORWARD),
                           ((key.S, key.DOWN), model.BACK),
                           ((key.A, key.LEFT), model.LEFT),
                           ((key.D, key.RIGHT), model.RIGHT),
                           ((key.Q,), model.UP), ((key.E,), model.DOWN)):
            if any(k[s] for s in keys):
                return port
        return None

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)
        run = self.run
        if run is not None and self.phase == self.PLAY and \
                buttons & mouse.LEFT:
            run.yaw += dx * 0.006
            run.pitch = max(-1.35, min(1.35, run.pitch + dy * 0.006))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height)
        lens = self.camera(run.eye(), model._look(run.yaw, run.pitch), left,
                           bottom, width, height)
        s = run.level.room
        g = self.layer()
        self.face(lens, [(0, 0, 0), (s, 0, 0), (s, 0, s), (0, 0, s)],
                  (26, 24, 22), g)
        self.face(lens, [(0, 2.8, 0), (0, 2.8, s), (s, 2.8, s), (s, 2.8, 0)],
                  (16, 16, 20), g)
        walls = [((0, 0), (s, 0)), ((s, 0), (s, s)), ((s, s), (0, s)),
                 ((0, s), (0, 0))]
        walls.sort(key=lambda w: -math.hypot((w[0][0] + w[1][0]) / 2 - run.x,
                                             (w[0][1] + w[1][1]) / 2 - run.z))
        for i, ((ax, az), (bx, bz)) in enumerate(walls):
            g = self.layer()
            shade = (34 + 6 * i, 34 + 6 * i, 44 + 6 * i)
            self.face(lens, [(ax, 0, az), (bx, 0, bz), (bx, 2.8, bz),
                             (ax, 2.8, az)], shade, g)
            self.seg(lens, (ax, 0.01, az), (bx, 0.01, bz), 2, (60, 60, 70), g)
        g = self.layer()
        for k in range(1, int(s)):
            self.seg(lens, (k, 0.005, 0), (k, 0.005, s), 1, (40, 38, 34), g)
            self.seg(lens, (0, 0.005, k), (s, 0.005, k), 1, (40, 38, 34), g)
        pieces = sorted(run.room.furniture, key=lambda f: -math.hypot(
            f[0] + f[2] / 2 - run.x, f[1] + f[3] / 2 - run.z))
        for x, z, w, d, h in pieces:
            self.box(lens, x, 0, z, x + w, h, z + d, (58, 48, 40), self.layer())
        g = self.layer()
        for k, c in enumerate(run.where):
            if run.caught[k]:
                self.ball(lens, c, 0.06, (120, 220, 130), g)
        # the aim
        cx, cy = left + width / 2, bottom + height / 2
        g = self.layer()
        self.line((cx - 10, cy), (cx + 10, cy), 1, (200, 200, 220, 120), g)
        self.line((cx, cy - 10), (cx, cy + 10), 1, (200, 200, 220, 120), g)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   caught %d of %d   grabs left %d') % (
            self.rung, self.trial, self.total_trials, sum(run.caught),
            len(run.caught), model.MISSES - run.misses)
