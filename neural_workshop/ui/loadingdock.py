# -*- coding: utf-8 -*-
"""Loading Dock on screen: the orders along the top, the warehouse under
them.

A concrete floor seen from one of the warehouse cameras. At the back,
the shelf: one bay for each kind of crate, lit when the forklift is
near enough to take from it. At the front, the trucks, each with its
city over it, a bar that runs down to when it leaves, the crates it has
been given on its bed, and a lamp that is green once its order is met.
The forklift is orange with its forks to the front and whatever it
carries stacked on them. From rung 16 a grey forklift works the floor
too.

Keys: Up / W forward, Down / S back, Left / A and Right / D turn.
Mouse: drag a crate from a lit bay to the forklift, and from the
forklift to a truck it is beside; click a truck's lamp to send it.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; ports 14-19 drive for the step they are sent
in: forward, back, turn left, turn right, forward-left, forward-right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import loadingdock as model
from ..i18n import _
from . import polish
from .handtask import HandTask

PAINT = ((214, 66, 58), (66, 116, 226), (66, 176, 96), (236, 204, 66))
CAMERAS = (_('CAM 1'), _('CAM 2'), _('CAM 3'), _('OVERHEAD'),
           _('BEHIND THE SHELF'))


class LoadingDock(HandTask):
    """Load every truck with its order and send it."""

    instance: Optional['LoadingDock'] = None

    TITLE = 'Loading Dock'
    TASK_ID = 'loading_dock'
    PREFIX = 'DOCK'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    BACK = (30, 34, 40)
    FOOTNOTE = _('Arrows / WASD: drive   Drag: crates, shelf to forklift '
                 'to truck   Click a lamp: send the truck   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Load each truck with its order, then send it')
        return ok

    def _held(self):
        k = self.keys
        on = set()
        if k[key.UP] or k[key.W]:
            on.add(model.FWD)
        if k[key.DOWN] or k[key.S]:
            on.add(model.BACK)
        if k[key.LEFT] or k[key.A]:
            on.add(model.LEFT)
        if k[key.RIGHT] or k[key.D]:
            on.add(model.RIGHT)
        return on or None

    def _g(self):
        self.layer += 1
        return pyglet.graphics.Group(order=self.layer)

    def _block(self, view, x, z, half_w, half_d, y0, y1, colour,
               turn=0.0) -> None:
        """A box, half_w across and half_d along its heading."""
        fx, fz = math.sin(turn), math.cos(turn)
        rx, rz = -fz, fx
        ring = [(x + a * half_w * rx + b * half_d * fx,
                 z + a * half_w * rz + b * half_d * fz)
                for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        quads = []
        for k in range(4):
            a, b = ring[k], ring[(k + 1) % 4]
            mid = view.see(((a[0] + b[0]) / 2, (y0 + y1) / 2,
                            (a[1] + b[1]) / 2))
            if mid is None:
                continue
            quads.append((-mid[2], k, [
                view.see((a[0], y0, a[1])), view.see((b[0], y0, b[1])),
                view.see((b[0], y1, b[1])), view.see((a[0], y1, a[1]))]))
        quads.sort()
        for n, (_d, k, pts) in enumerate(quads):
            self.poly(pts, polish.mix((0, 0, 0), colour,
                                      0.55 + 0.15 * n), self._g())
        self.poly([view.see((p[0], y1, p[1])) for p in ring],
                  polish.mix(colour, (255, 255, 255), 0.15), self._g())

    def _crate(self, view, kind, x, y, z, size=0.55) -> None:
        self._block(view, x, z, size, size, y, y + 2 * size,
                    PAINT[kind.colour])
        if kind.tag:
            q = view.see((x, y + 2 * size + 0.02, z))
            if q is not None:
                self.words(model.MARKS[kind.tag], q[0], q[1], 13,
                           group=self._g(), bold=True,
                           colour=(255, 255, 255, 255) if kind.colour != 3
                           else (30, 30, 30, 255))

    def _scene(self, run, s: float) -> None:
        view = run.view()
        see = view.see
        dock = run.dock
        self.layer = 0
        W, D = model.WIDE + 1.5, 9.0
        self.poly([see((-W, 0, -D)), see((W, 0, -D)), see((W, 0, D)),
                   see((-W, 0, D))], (112, 116, 122), self._g())
        for x in (-6, -2, 2, 6):
            self.line(see((x, 0.01, -model.DEEP)), see((x, 0.01, model.DEEP)),
                      2, (236, 204, 66, 90), self._g())
        things = []

        def add(point, what, *more):
            q = see(point)
            if q is not None:
                things.append((-q[2], len(things), what) + more)

        for k in range(len(dock.shelf)):
            add(run.slot(k), 'slot', k)
        for k in run.waiting():
            add(run.bed(k), 'truck', k)
        add(run.fork(), 'fork')
        other = run.other()
        if other is not None:
            add((other[0], 0.5, other[1]), 'other', other)
        things.sort()
        for item in things:
            what = item[2]
            if what == 'slot':
                self._slot(view, run, item[3])
            elif what == 'truck':
                self._truck(view, run, item[3])
            elif what == 'fork':
                self._fork(view, run.p[0], run.p[1], run.heading,
                           (240, 140, 40), run.carried)
            else:
                x, z, heading = item[3]
                self._fork(view, x, z, heading, (130, 140, 156), [])
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        if run.drag is not None:
            kind = run.drag[1]
            self.rect(run.hand.x - 16, run.hand.y - 16, 32, 32,
                      PAINT[kind.colour], hud)
            if kind.tag:
                self.words(model.MARKS[kind.tag], run.hand.x, run.hand.y, 13,
                           group=text, bold=True,
                           colour=(255, 255, 255, 255) if kind.colour != 3
                           else (30, 30, 30, 255))
        waiting = sorted(run.waiting(), key=lambda k: dock.trucks[k].leave)
        rows = max(1, len(waiting))
        tall = 20 + 24 * rows
        self.rect(20, 628 - tall, 960, tall, (16, 18, 28, 225), hud)
        for n, k in enumerate(waiting):
            done = run.complete(k)
            self.words(dock.trucks[k].text + ('   ' + _('(ready: send it)')
                                              if done else ''),
                       500, 628 - 22 - 24 * n, 15, bold=True, group=text,
                       colour=(140, 240, 160, 255) if done
                       else (255, 255, 255, 255))
        self.words(CAMERAS[run.cam], 80, 30, 11, bold=True, group=text,
                   colour=(255, 255, 255, 200))
        self.words(_('sent %d of %d') % (sum(run.sent), len(dock.trucks)),
                   920, 30, 11, group=text, colour=(255, 255, 255, 200))

    def _slot(self, view, run, k) -> None:
        x, _y, z = run.slot(k)
        near = run.near_slot(k)
        self._block(view, x, z, 0.95, 0.8, 0.0, 0.35,
                    (220, 200, 110) if near else (84, 88, 98))
        if run.stocked(k):
            self._crate(view, run.dock.shelf[k], x, 0.35, z)

    def _truck(self, view, run, k) -> None:
        truck = run.dock.trucks[k]
        x, _y, z = run.bed(k)
        self._block(view, x, z, 1.9, 1.5, 0.5, 1.0, (70, 76, 90))
        for n, kind in enumerate(run.loads[k]):
            self._crate(view, kind, x - 1.1 + 1.1 * n, 1.0, z, 0.45)
        self._block(view, x + 2.5, z + 0.3, 0.7, 1.1, 0.4, 2.6,
                    (200, 206, 216))
        lamp = view.see(run.lamp(k))
        if lamp is not None:
            colour = (90, 230, 120) if run.complete(k) else (240, 170, 60)
            ax, ay = self.px(lamp[0], lamp[1])
            polish.glow(self.drawn, self.batch, ax, ay,
                        30 * self.fit[2], colour, strength=70,
                        group=self._g())
            self.disc(lamp, 12, colour, self._g())
        q = view.see((x, 3.4, z))
        if q is not None:
            self.words(truck.city, q[0], q[1], 14, bold=True,
                       group=self._g(), colour=(255, 255, 255, 255))
            span = max(1e-6, truck.leave - truck.arrive)
            share = max(0.0, min(1.0, (truck.leave - run.t) / span))
            hurry = truck.leave - run.t < model.HORN_AHEAD
            self.rect(q[0] - 35, q[1] - 18, 70 * share, 4,
                      (240, 80, 60) if hurry else (200, 210, 230),
                      self._g())

    def _fork(self, view, x, z, heading, colour, carried) -> None:
        fx, fz = math.sin(heading), math.cos(heading)
        parts = [(0, 'body'), (1, 'mast')]
        if view.see((x + fx, 0.5, z + fz))[2] > view.see((x, 0.5, z))[2]:
            parts.reverse()                 # the forks are the far end
        for _n, part in parts:
            if part == 'body':
                self._block(view, x - 0.25 * fx, z - 0.25 * fz, 0.6, 0.75,
                            0.15, 1.0, colour, heading)
                self._block(view, x - 0.55 * fx, z - 0.55 * fz, 0.55, 0.4,
                            1.0, 1.7, (50, 54, 64), heading)
                continue
            for side in (-0.35, 0.35):
                rx, rz = -fz * side, fx * side
                self.line(view.see((x + 0.6 * fx + rx, 0.15, z + 0.6 * fz
                                    + rz)),
                          view.see((x + 1.5 * fx + rx, 0.15, z + 1.5 * fz
                                    + rz)), 4, (40, 42, 50), self._g())
                self.line(view.see((x + 0.6 * fx + rx, 0.1, z + 0.6 * fz
                                    + rz)),
                          view.see((x + 0.6 * fx + rx, 2.1, z + 0.6 * fz
                                    + rz)), 4, (40, 42, 50), self._g())
            for n, kind in enumerate(carried):
                self._crate(view, kind, x + 1.15 * fx, 0.2 + 0.95 * n,
                            z + 1.15 * fz, 0.45)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   carrying %d of %d') % (
            self.rung, self.trial, self.total_trials, len(run.carried),
            model.CARRY)
