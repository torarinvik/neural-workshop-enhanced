# -*- coding: utf-8 -*-
"""Rover on screen: the rover's own chase camera, as it was.

The picture is late by half the delay: what the rover saw then. The
bar along the bottom shows the commands still on their way, and the
signal's delay is written beside it.

W / Up drive, S / Down brake and back up, A / D or Left / Right steer.

For the agent boundary: ports 0-3 drive, brake, steer left and right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key

from .. import rover as model
from ..i18n import _
from .livetask import LiveTask

TINTS = {model.DRIVE: (110, 220, 140), model.BRAKE: (230, 110, 90),
         model.LEFT: (120, 170, 250), model.RIGHT: (240, 200, 90)}


class Rover(LiveTask):
    """Drive to every flag; every signal is late."""

    instance: Optional['Rover'] = None

    TITLE = 'Rover'
    TASK_ID = 'rover'
    PREFIX = 'ROVER'
    CATEGORY = 'planning'
    MODEL = model
    BACK = (40, 26, 22)
    FOOTNOTE = _('W: drive   S: brake / back   A / D: steer   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Drive to each flag. Everything you see and send '
                         'is late')
        return ok

    def _held(self):
        k = self.keys
        for keys, port in (((key.W, key.UP), model.DRIVE),
                           ((key.S, key.DOWN), model.BRAKE),
                           ((key.A, key.LEFT), model.LEFT),
                           ((key.D, key.RIGHT), model.RIGHT)):
            if any(k[s] for s in keys):
                return port
        return None

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        g0 = run.g
        self.frame(left, bottom, width, height, (176, 120, 96))
        s = run.seen()
        fx, fz = math.sin(s.heading), math.cos(s.heading)
        ground = model.height(g0, s.x, s.z)
        eye = (s.x - 9 * fx, ground + 3.4, s.z - 9 * fz)
        look = (12 * fx, -1.6, 12 * fz)
        lens = self.camera(eye, look, left, bottom, width, height, 64)
        # the sky above the horizon
        h = lens.see((eye[0] + 900 * fx, eye[1], eye[2] + 900 * fz))
        if h is not None and h[1] < bottom + height:
            self.rect(left, max(bottom, h[1]), width,
                      bottom + height - max(bottom, h[1]), (214, 168, 132),
                      self.layer())
        # the ground, far to near
        g = self.layer()
        cell = 2.5
        cx0, cz0 = round(s.x / cell) * cell, round(s.z / cell) * cell
        quads = []
        for i in range(-12, 13):
            for j in range(-12, 13):
                x, z = cx0 + i * cell, cz0 + j * cell
                ahead = (x - eye[0]) * fx + (z - eye[2]) * fz
                if ahead < -2:
                    continue
                pts = [(x, model.height(g0, x, z), z),
                       (x + cell, model.height(g0, x + cell, z), z),
                       (x + cell, model.height(g0, x + cell, z + cell),
                        z + cell),
                       (x, model.height(g0, x, z + cell), z + cell)]
                rise = (pts[1][1] - pts[0][1]) - (pts[3][1] - pts[0][1])
                shade = max(0.55, min(1.15, 0.9 + 0.5 * rise / cell))
                base = (196, 132, 98) if (i + j) % 2 else (188, 126, 94)
                d = math.hypot(x - eye[0], z - eye[2])
                quads.append((d, pts, tuple(min(255, int(c * shade))
                                            for c in base)))
        for _d, pts, colour in sorted(quads, key=lambda q: -q[0]):
            self.face(lens, pts, colour, g)
        # rocks, flags and the rover, far to near
        things = []
        reach = 12 * cell - 2
        for rx, rz, rr in g0.rocks:
            if abs(rx - cx0) > reach or abs(rz - cz0) > reach:
                continue
            things.append((math.hypot(rx - eye[0], rz - eye[2]), 'rock',
                           (rx, rz, rr)))
        for k, (px, pz) in enumerate(g0.flags):
            if k >= run.reached:
                things.append((math.hypot(px - eye[0], pz - eye[2]), 'flag',
                               (px, pz, k)))
        things.append((math.hypot(s.x - eye[0], s.z - eye[2]), 'rover', s))
        g = self.layer()
        for _d, kind, it in sorted(things, key=lambda q: -q[0]):
            if kind == 'rock':
                rx, rz, rr = it
                y = model.height(g0, rx, rz)
                self.ball(lens, (rx, y + rr * 0.6, rz), rr, (110, 82, 70), g)
            elif kind == 'flag':
                px, pz, k = it
                y = model.height(g0, px, pz)
                colour = (250, 240, 90) if k == run.reached else \
                    (200, 200, 210)
                self.seg(lens, (px, y, pz), (px, y + 3.2, pz), 3,
                         (240, 240, 245), g)
                self.face(lens, [(px, y + 3.2, pz), (px + 1.2, y + 2.85, pz),
                                 (px, y + 2.5, pz)], colour, g)
                self.face(lens, [(px + math.cos(a) * model.FLAG,
                                  y + 0.05, pz + math.sin(a) * model.FLAG)
                                 for a in (k2 * math.pi / 8
                                           for k2 in range(16))],
                          (210, 150, 110), g)
            else:
                self._rover(lens, g0, it, g)
        self._tray(run, left, bottom, width)

    def _rover(self, lens, g0, s, g) -> None:
        fx, fz = math.sin(s.heading), math.cos(s.heading)
        rx, rz = fz, -fx
        y = model.height(g0, s.x, s.z) + 0.35

        def at(a, b, up):
            return (s.x + fx * a + rx * b, y + up, s.z + fz * a + rz * b)

        for a, b in ((0.8, 0.75), (0.8, -0.75), (-0.8, 0.75), (-0.8, -0.75)):
            self.ball(lens, at(a, b, 0.0), 0.35, (50, 50, 56), g)
        body = [at(1.1, 0.6, 0.5), at(1.1, -0.6, 0.5), at(-1.1, -0.6, 0.5),
                at(-1.1, 0.6, 0.5)]
        low = [at(1.1, 0.6, 0.15), at(1.1, -0.6, 0.15),
               at(-1.1, -0.6, 0.15), at(-1.1, 0.6, 0.15)]
        self.face(lens, [low[2], low[3], body[3], body[2]], (190, 190, 200), g)
        self.face(lens, [low[3], low[0], body[0], body[3]], (170, 170, 182), g)
        self.face(lens, [low[1], low[2], body[2], body[1]], (170, 170, 182), g)
        self.face(lens, body, (232, 232, 240), g)
        self.seg(lens, at(-0.6, 0.0, 0.5), at(-0.6, 0.0, 1.4), 2,
                 (90, 90, 100), g)
        self.ball(lens, at(-0.6, 0.0, 1.45), 0.12, (240, 240, 250), g)

    def _tray(self, run, left, bottom, width) -> None:
        """The commands still on their way, by when they land."""
        g = self.layer()
        delay = model.delay_at(run.g, run.t)
        w = width - 220
        x0, y0 = left + 110, bottom + 14
        self.rect(x0, y0, w, 14, (30, 22, 20, 200), g)
        span = max(0.2, delay / 2)
        for at, port, _dur in run.queue:
            u = 1 - (at - run.t) / span
            self.rect(x0 + w * max(0.0, min(1.0, u)) - 2, y0 + 1, 4, 12,
                      TINTS.get(port, (255, 255, 255)), g)
        self.say(_('delay %.1f s') % delay, x0 - 54, y0 + 7, 12,
                 (250, 236, 220, 255))
        self.say(_('rover'), x0 + w + 30, y0 + 7, 12, (250, 236, 220, 255))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   flags %d/%d') % (
            self.rung, self.trial, self.total_trials, self.run.reached,
            len(self.run.g.flags))
