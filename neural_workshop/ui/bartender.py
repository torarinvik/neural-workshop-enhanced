# -*- coding: utf-8 -*-
"""Bartender on screen: the bar from behind it, one glass, a row of
bottles.

The bottles stand on the shelf at the left, the glass on the bar in
front of them, and the bar runs away to the right past the numbered
seats. A customer who is waiting sits at their seat under what they
ordered, with a bar that runs down as their patience does. The glass
shows how full it is, unless the rung pours into pewter. Strikes are
the marks in the corner.

Mouse: hold a bottle over the glass to pour; drag the glass back and
let it go to slide it, further back for a longer slide. Keys: Space
puts ice in or takes it out.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 is the ice.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import bartender as model
from ..i18n import _
from . import polish
from .handtask import HandTask

DRINK = ((214, 60, 54), (60, 170, 90), (70, 110, 220), (226, 160, 50),
         (160, 90, 200))
HAT = ((30, 30, 34), (240, 240, 240), (130, 90, 50), (140, 140, 150),
       (50, 130, 70))


class Bartender(HandTask):
    """Pour what was ordered and slide it to the right seat."""

    instance: Optional['Bartender'] = None

    TITLE = 'Bartender'
    TASK_ID = 'bartender'
    PREFIX = 'BAR'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.SPACE: model.ICE, key.I: model.ICE}
    BACK = (30, 22, 20)
    TIME_BAR = False
    FOOTNOTE = _('Hold a bottle over the glass: pour   Drag the glass back '
                 'and let go: slide   Space: ice   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Serve every customer before they walk out')
        return ok

    def _bottle(self, x, y, k, size) -> None:
        self.rect(x - 0.5 * size, y - size, size, 2.0 * size, DRINK[k],
                  self.g())
        self.rect(x - 0.18 * size, y + size, 0.36 * size, 0.8 * size,
                  polish.mix((0, 0, 0), DRINK[k], 0.7), self.g())
        self.rect(x - 0.5 * size, y - 0.3 * size, size, 0.6 * size,
                  (240, 236, 220), self.g())

    def _scene(self, run, s: float) -> None:
        m, view, level = model, model.VIEW, run.level
        see = view.see
        top = m.TOP
        self.rect(0, 0, 1000, 640, (56, 36, 30), self.g())
        for k in range(12):                                 # panelling
            self.rect(84 * k, 330, 4, 310, (46, 30, 26), self.g())
        self.poly([see((-2.4, 1.6, -1.6)), see((2.2, 1.6, -1.6)),
                   see((2.2, 1.6, -1.0)), see((-2.4, 1.6, -1.0))],
                  (110, 76, 50), self.g())                  # the shelf
        for k in range(level.bottles):
            if run.held == ('bottle', k):
                continue
            q = see(m.bottle_at(k))
            if q is not None:
                self._bottle(q[0], q[1], k, view.size(0.34, q[2]))
        waiting = run.waiting()
        for k in waiting:                                   # customers
            o = run.night.orders[k]
            x = m.SEATS[o.seat]
            foot, head = see((x, top, -0.7)), see((x, top + 1.0, -0.7))
            if foot is None or head is None:
                continue
            wide = view.size(0.42, foot[2])
            self.poly([(foot[0] - wide, foot[1]), (foot[0] + wide, foot[1]),
                       (head[0] + 0.8 * wide, head[1]),
                       (head[0] - 0.8 * wide, head[1])], (90, 100, 130),
                      self.g())
            self.disc((head[0], head[1] + 0.6 * wide), 0.62 * wide,
                      (236, 200, 170), self.g())
            self.rect(head[0] - 0.9 * wide, head[1] + 0.95 * wide,
                      1.8 * wide, 0.2 * wide, HAT[o.hat], self.g())
            self.rect(head[0] - 0.55 * wide, head[1] + 1.1 * wide,
                      1.1 * wide, 0.6 * wide, HAT[o.hat], self.g())
        self.poly([see((-2.8, top, -0.2)), see((m.END, top, -0.2)),
                   see((m.END, top, 1.0)), see((-2.8, top, 1.0))],
                  (150, 96, 56), self.g())                  # the bar top
        self.poly([see((-2.8, top, 1.0)), see((m.END, top, 1.0)),
                   see((m.END, 0.0, 1.0)), see((-2.8, 0.0, 1.0))],
                  (96, 60, 38), self.g())
        self.poly([see((m.STATION[0] - 0.3, top + 0.005, 0.0)),
                   see((m.STATION[1] + 0.3, top + 0.005, 0.0)),
                   see((m.STATION[1] + 0.3, top + 0.005, 0.8)),
                   see((m.STATION[0] - 0.3, top + 0.005, 0.8))],
                  (170, 116, 70), self.g())                 # your station
        for n, x in enumerate(m.SEATS):
            q = see((x, top - 0.45, 1.0))
            if q is not None:
                self.words('%d' % (n + 1), q[0], q[1], 16, bold=True,
                           group=self.g(), colour=(250, 230, 190, 255))
            self.line(see((x - 0.55, top + 0.01, 0.05)),
                      see((x + 0.55, top + 0.01, 0.05)), 3,
                      (250, 230, 190, 160), self.g())
        base, lip = see((run.glass_x, top, 0.4)), see((run.glass_x,
                                                        top + 0.6, 0.4))
        if base is not None and lip is not None:            # the glass
            wide = view.size(0.2, base[2])
            tall = lip[1] - base[1]
            pewter = level.pewter
            self.poly([(base[0] - 0.8 * wide, base[1]),
                       (base[0] + 0.8 * wide, base[1]),
                       (lip[0] + wide, lip[1]), (lip[0] - wide, lip[1])],
                      (150, 154, 166) if pewter else (210, 226, 236, 110),
                      self.g())
            if not pewter and run.level_in > 0:
                f = min(1.0, run.level_in)
                tint = DRINK[run.drink] if run.drink >= 0 else (90, 70, 60)
                self.poly([(base[0] - 0.8 * wide, base[1]),
                           (base[0] + 0.8 * wide, base[1]),
                           (base[0] + (0.8 + 0.2 * f) * wide,
                            base[1] + tall * f),
                           (base[0] - (0.8 + 0.2 * f) * wide,
                            base[1] + tall * f)], tint, self.g())
            if level.rung < 7 and not pewter:
                for lo, hi in (m.SINGLE, m.DOUBLE):
                    for v in (lo, hi):
                        self.line((base[0] - wide, base[1] + tall * v),
                                  (base[0] - 0.6 * wide,
                                   base[1] + tall * v), 2,
                                  (255, 255, 255, 220), self.g())
            if run.ice:
                for dx in (-0.4, 0.3):
                    self.rect(base[0] + dx * wide, lip[1] - 0.3 * wide,
                              0.4 * wide, 0.4 * wide, (240, 250, 255),
                              self.g())
        if run.held is not None and run.held[0] == 'bottle':
            k = run.held[1]
            self._bottle(run.hand.x, run.hand.y + 30, k, 20)
            g = view.see(run.glass())
            if g is not None and abs(run.hand.x - g[0]) < m.OVER and \
                    abs(run.hand.y - g[1]) < m.OVER:
                self.line((run.hand.x, run.hand.y + 8), (g[0], g[1]), 3,
                          DRINK[k], self.g())
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        for row, k in enumerate(waiting[:4]):
            o = run.night.orders[k]
            y = 612 - 30 * row
            self.rect(250, y - 13, 730, 26, (16, 14, 18, 215), hud)
            self.words(o.text, 262, y, 13, anchor='left', bold=row == 0,
                       group=text, colour=(255, 255, 255, 255))
            share = max(0.0, (o.leave - run.t) / (o.leave - o.arrive))
            self.rect(860, y - 4, 110 * share, 8,
                      polish.mix((236, 80, 64), (110, 220, 140), share),
                      text)
        for k in range(level.strikes):
            self.disc((40 + 26 * k, 610), 8, (236, 80, 64)
                      if k < run.strikes else (70, 56, 50), text)
        self.words(_('%d of %d served') % (sum(run.served),
                                           len(run.served)), 110, 580, 12,
                   group=text, colour=(240, 230, 220, 255))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d customers') % (
            self.rung, self.trial, self.total_trials, run.level.customers)
