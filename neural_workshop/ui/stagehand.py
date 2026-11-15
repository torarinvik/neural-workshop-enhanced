# -*- coding: utf-8 -*-
"""Stagehand on screen: the script along the top, the stage under it.

A wooden stage with a mark for every place a prop can stand, a back
wall with curtains, the props drawn as what they are -- a chair with a
back, a table on four legs, a standing lamp, a crate, a plant in a pot,
a barrel -- and the actor, a figure in blue. The prop in the spotlight
stands in a pool of light. The corner says which seat the camera is in.
A bar under the script runs down while a line's moment lasts.

Mouse: drag a prop to another mark; click a prop to put the spotlight
on it. Keys: L lights, C curtain, M music, S smoke, T thunder.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; ports 14-18 are the keys L, C, M, S and T.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import stagehand as model
from ..i18n import _
from . import polish
from .handtask import HandTask

SEATS = (_('CENTRE'), _('LEFT BOX'), _('RIGHT BOX'), _('BALCONY'),
         _('BACKSTAGE'))
WOOD = (150, 112, 76)
KEYS = {key.L: model.KEY, key.C: model.KEY + 1, key.M: model.KEY + 2,
        key.S: model.KEY + 3, key.T: model.KEY + 4}


class Stagehand(HandTask):
    """Do each line of the script, in its moment."""

    instance: Optional['Stagehand'] = None

    TITLE = 'Stagehand'
    TASK_ID = 'stagehand'
    PREFIX = 'STAGE'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = KEYS
    BACK = (22, 18, 26)
    FOOTNOTE = _('Drag: move a prop   Click: spotlight   L lights  C curtain'
                 '  M music  S smoke  T thunder   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Follow the script: left and right are the '
                         "audience's")
        return ok

    def _g(self):
        self.layer += 1
        return pyglet.graphics.Group(order=self.layer)

    def _prism(self, view, x, z, half, y0, y1, sides, colour, turn=0.0):
        """An upright prism, far sides first, then its top."""
        ring = [(x + half * math.cos(a), z + half * math.sin(a))
                for a in (turn + 2 * math.pi * k / sides
                          for k in range(sides))]
        quads = []
        for k in range(sides):
            a, b = ring[k], ring[(k + 1) % sides]
            mid = view.see(((a[0] + b[0]) / 2, (y0 + y1) / 2,
                            (a[1] + b[1]) / 2))
            if mid is None:
                continue
            quads.append((-mid[2], k, [
                view.see((a[0], y0, a[1])), view.see((b[0], y0, b[1])),
                view.see((b[0], y1, b[1])), view.see((a[0], y1, a[1]))]))
        quads.sort()
        for n, (_d, k, pts) in enumerate(quads):
            shade = 0.55 + 0.45 * (n / max(1, len(quads) - 1))
            self.poly(pts, polish.mix((0, 0, 0), colour, shade), self._g())
        self.poly([view.see((p[0], y1, p[1])) for p in ring],
                  polish.mix(colour, (255, 255, 255), 0.18), self._g())

    def _scene(self, run, s: float) -> None:
        view = run.view()
        see = view.see
        self.layer = 0
        bright = 1.0 if run.on[0] else 0.8
        tone = lambda c: polish.mix((0, 0, 0), c, bright)   # noqa: E731
        wide, back, front = 6.6, -4.2, 4.4
        floor = [see((-wide, 0, back)), see((wide, 0, back)),
                 see((wide, 0, front)), see((-wide, 0, front))]
        self.poly(floor, tone(WOOD), self._g())
        if run.cam != 4:
            wall = [see((-wide, 0, back)), see((wide, 0, back)),
                    see((wide, 5.0, back)), see((-wide, 5.0, back))]
            self.poly(wall, tone((70, 40, 60)), pyglet.graphics.Group(order=-1))
            reach = 2.6 if run.on[1] else 1.0
            for side in (-1, 1):
                drape = [see((side * wide, 0, back + 0.05)),
                         see((side * (wide - reach), 0, back + 0.05)),
                         see((side * (wide - reach), 5.0, back + 0.05)),
                         see((side * wide, 5.0, back + 0.05))]
                self.poly(drape, tone((170, 40, 50)), self._g())
        for c in range(model.COLS):
            for r in range(model.ROWS):
                x, z = model.spot_of((c, r))
                self.line(see((x - 0.25, 0.01, z)), see((x + 0.25, 0.01, z)),
                          2, (240, 230, 200, 150), self._g())
                self.line(see((x, 0.01, z - 0.25)), see((x, 0.01, z + 0.25)),
                          2, (240, 230, 200, 150), self._g())
        things = []
        for p in range(len(run.at)):
            x, z = run.place(p)
            q = see((x, 0.0, z))
            if q is not None:
                things.append((-q[2], 'prop', p, x, z))
        ax, az = run.actor
        q = see((ax, 0.0, az))
        if q is not None:
            things.append((-q[2], 'actor', -1, ax, az))
        things.sort()
        for _d, what, p, x, z in things:
            if what == 'actor':
                self._prism(view, x, z, 0.28, 0.0, 1.25, 6, tone((60, 100,
                                                                 200)))
                self.disc(see((x, 1.5, z)), 9, tone((236, 200, 170)),
                          self._g())
                continue
            if run.lit == p:
                pool = [see((x + 1.0 * math.cos(a), 0.02,
                             z + 1.0 * math.sin(a)))
                        for a in (2 * math.pi * k / 16 for k in range(16))]
                self.poly(pool, (255, 240, 170, 120), self._g())
            self._prop(view, run.show.props[p], x, z, tone)
            if run.level.rung < 4:
                at = see((x, -0.0, z + 0.75))
                if at is not None:
                    self.words(model.PROPS[run.show.props[p]], at[0], at[1],
                               11, group=self._g(),
                               colour=(255, 255, 255, 230))
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        if run.on[3]:
            self.rect(0, 0, 1000, 540, (220, 220, 230, 60), hud)
        self.rect(20, 548, 960, 80, (16, 18, 28, 225), hud)
        line = run.line
        self.words(line.text if line else '', 500, 602, 18, bold=True,
                   colour=(255, 255, 255, 255), group=text)
        lines = run.show.lines
        if 0 <= run.line_no + 1 < len(lines):
            self.words(_('next: ') + lines[run.line_no + 1].text, 500, 572,
                       11, colour=(170, 180, 200, 255), group=text)
        if line is not None and run.open():
            span = max(1e-6, run.due - run.opens)
            share = max(0.0, min(1.0, (run.due - run.t) / span))
            self.rect(250, 552, 500 * share, 5, (255, 200, 70), text)
        self.words(SEATS[run.cam], 70, 528, 11, bold=True,
                   colour=(255, 255, 255, 200), group=text)
        self.words(_('line %d of %d') % (min(run.line_no + 1, len(lines)),
                                         len(lines)), 930, 528, 11,
                   colour=(255, 255, 255, 200), group=text)

    def _prop(self, view, kind, x, z, tone) -> None:
        see = view.see
        if kind == 0:                                   # chair
            for dx in (-0.3, 0.3):
                for dz in (-0.3, 0.3):
                    self.line(see((x + dx, 0, z + dz)),
                              see((x + dx, 0.5, z + dz)), 3,
                              tone((90, 60, 40)), self._g())
            self._prism(view, x, z, 0.45, 0.5, 0.6, 4, tone((170, 110, 60)),
                        math.pi / 4)
            back = [see((x - 0.32, 0.6, z - 0.3)), see((x + 0.32, 0.6,
                                                        z - 0.3)),
                    see((x + 0.32, 1.35, z - 0.3)), see((x - 0.32, 1.35,
                                                         z - 0.3))]
            self.poly(back, tone((150, 95, 50)), self._g())
        elif kind == 1:                                 # table
            for dx in (-0.55, 0.55):
                for dz in (-0.4, 0.4):
                    self.line(see((x + dx, 0, z + dz)),
                              see((x + dx, 0.85, z + dz)), 4,
                              tone((70, 70, 80)), self._g())
            self._prism(view, x, z, 0.85, 0.85, 0.97, 4, tone((200, 200,
                                                               210)),
                        math.pi / 4)
        elif kind == 2:                                 # lamp
            self._prism(view, x, z, 0.3, 0.0, 0.08, 8, tone((60, 60, 70)))
            self.line(see((x, 0.08, z)), see((x, 1.7, z)), 4,
                      tone((60, 60, 70)), self._g())
            self._prism(view, x, z, 0.42, 1.55, 2.0, 8, (250, 220, 110))
        elif kind == 3:                                 # crate
            self._prism(view, x, z, 0.62, 0.0, 0.88, 4, tone((190, 150, 90)),
                        math.pi / 4)
        elif kind == 4:                                 # plant
            self._prism(view, x, z, 0.3, 0.0, 0.45, 6, tone((180, 90, 60)))
            for dy, r in ((0.75, 17), (1.05, 14), (1.3, 10)):
                self.disc(see((x, dy, z)), r, tone((60, 160, 80)), self._g())
        else:                                           # barrel
            self._prism(view, x, z, 0.48, 0.0, 1.05, 10, tone((120, 60, 50)))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d props') % (
            self.rung, self.trial, self.total_trials, len(run.at))
