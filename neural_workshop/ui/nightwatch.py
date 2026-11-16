# -*- coding: utf-8 -*-
"""Night Watch on screen: the dark, and the round of light you carry.

The warehouse is black but for the lamp on the safe and the faint
shapes of the crates. Your torch lights a round patch at the pointer,
and whoever stands in it: a figure in a cap of some colour, or the
cat. The night's orders are along the top, with the whistle blasts you
have left and your strikes. When the floor is wider than the view,
arrows at the sides show there is more that way.

Mouse: the torch; click a thief to catch them. Keys: Left / A and
Right / D turn you along the floor.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; ports 14 and 15, held, turn the view left
and right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import nightwatch as model
from ..i18n import _
from .handtask import HandTask

CAP = {'red': (226, 60, 54), 'green': (60, 180, 90), 'blue': (70, 120, 230),
       'yellow': (240, 210, 60), 'white': (240, 240, 240),
       'grey': (130, 130, 140)}


class NightWatch(HandTask):
    """Catch every thief before one reaches the safe."""

    instance: Optional['NightWatch'] = None

    TITLE = 'Night Watch'
    TASK_ID = 'night_watch'
    PREFIX = 'WATCH'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    BACK = (6, 6, 10)
    FOOTNOTE = _('Mouse: the torch   Click a thief   Left/Right or A/D: '
                 'turn along the floor   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = self.run.orders()
        return ok

    def _held(self):
        k = self.keys
        if k[key.LEFT] or k[key.A]:
            return model.LEFT
        if k[key.RIGHT] or k[key.D]:
            return model.RIGHT
        return None

    def _scene(self, run, s: float) -> None:
        m, level = model, run.level
        view = run.view()
        see = view.see
        half = level.half
        self.rect(0, 0, 1000, 640, (8, 8, 12), self.g())
        self.poly([see((-half - 2, 0, 0)), see((half + 2, 0, 0)),
                   see((half + 2, 0, m.DEEP + 3)),
                   see((-half - 2, 0, m.DEEP + 3))], (16, 16, 22), self.g())
        hx, hy = run.hand.x, run.hand.y
        for k in range(int(half) * 2):                      # crates
            x = -half + 1.0 + (k * 2.618) % (2 * half - 2.0)
            z = 0.3 if k % 2 else m.DEEP - 0.2
            a, b = see((x - 0.5, 0, z)), see((x + 0.5, 1.0 + 0.4 * (k % 3),
                                              z))
            if a is not None and b is not None:
                self.poly([(a[0], a[1]), (b[0], a[1]), (b[0], b[1]),
                           (a[0], b[1])], (26, 24, 26), self.g())
        self.disc((hx, hy), level.beam, (210, 196, 150, 60), self.g())
        self.disc((hx, hy), level.beam * 0.72, (255, 240, 200, 60),
                  self.g())
        q = see((m.SAFE[0], 0.0, m.SAFE[1]))
        if q is not None:                                   # the safe
            u = 760.0 / q[2]
            self.rect(q[0] - 0.45 * u, q[1], 0.9 * u, 1.0 * u, (44, 48, 60),
                      self.g())
            self.disc((q[0], q[1] + 0.5 * u), 0.16 * u, (90, 96, 110),
                      self.g())
            self.disc((q[0], q[1] + 1.12 * u), 0.07 * u, (90, 230, 120),
                      self.g())
        seen = []
        for k in range(len(run.night.walkers)):
            if run.lit(k):
                seen.append((run.spot(k), k))
        seen.sort(key=lambda p: p[0][2])
        for (x, y, u), k in seen:
            w = run.night.walkers[k]
            if w.kind == m.CAT:
                self.oval((x, y), 0.42 * u, 0.2 * u, (120, 120, 130),
                          self.g())
                self.disc((x + 0.36 * u, y + 0.2 * u), 0.15 * u,
                          (120, 120, 130), self.g())
                self.line((x - 0.4 * u, y), (x - 0.6 * u, y + 0.4 * u), 3,
                          (120, 120, 130), self.g())
                continue
            self.rect(x - 0.24 * u, y - 1.0 * u, 0.48 * u, 0.65 * u,
                      (40, 40, 52), self.g())
            self.rect(x - 0.3 * u, y - 0.35 * u, 0.6 * u, 0.85 * u,
                      (64, 66, 84), self.g())
            self.disc((x, y + 0.7 * u), 0.2 * u, (226, 190, 160), self.g())
            self.rect(x - 0.24 * u, y + 0.8 * u, 0.48 * u, 0.16 * u,
                      CAP[w.colour], self.g())
            self.rect(x - 0.24 * u, y + 0.8 * u, 0.7 * u, 0.06 * u,
                      CAP[w.colour], self.g())
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        self.rect(150, 600, 700, 32, (20, 20, 28, 230), hud)
        self.words(run.orders(), 500, 616, 13, bold=True, group=text,
                   colour=(255, 255, 255, 255))
        self.words(_('caught %d / %d') % (run.caught, level.thieves), 80,
                   570, 12, group=text, colour=(220, 220, 230, 255))
        self.words(_('whistle: %d') % run.blasts, 80, 548, 12, group=text,
                   colour=(220, 220, 230, 255))
        for k in range(level.strikes):
            self.disc((40 + 24 * k, 524), 7, (236, 80, 64)
                      if k < run.strikes else (40, 40, 50), text)
        room = run.room()
        if room > 0:
            if run.cam > -room + 0.05:
                self.words('<  A', 40, 320, 16, bold=True, group=text,
                           colour=(200, 200, 210, 200))
            if run.cam < room - 0.05:
                self.words('D  >', 960, 320, 16, bold=True, group=text,
                           colour=(200, 200, 210, 200))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d thieves') % (
            self.rung, self.trial, self.total_trials, run.level.thieves)
