# -*- coding: utf-8 -*-
"""Balance on screen: a handcar in a fenced yard at dusk, a lantern pole
on top, seen from behind and above.

Hold the arrow keys (or W A S D) to push the cart left, right, away and
near; the pole carries a lantern and leans the other way. Its shadow on
the ground shows which way it leans. A gauge in the corner reads the
lean from above: the dot is the lantern, and the ring's edge is the
ground. Flags stand in the yard; the one to stop under is lit, a ring
fills while the cart holds still there, and a map in the other corner
shows where they all are. Dust streaks show the gusts.

For the agent boundary: ports 0-3 push the cart left, right, away and
near for one step.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key

from .. import balance as model
from ..i18n import _
from . import polish
from .livetask import LiveTask

FLAGS = ((236, 72, 80), (60, 150, 236), (250, 196, 50), (90, 200, 120),
         (180, 100, 230), (240, 130, 60))
DECK = 0.9                     # the cart's deck, where the pole is hinged


class Balance(LiveTask):
    """Every flag in turn, the lantern never on the ground."""

    instance: Optional['Balance'] = None

    TITLE = 'Balance'
    TASK_ID = 'balance'
    PREFIX = 'BALANCE'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    BACK = (236, 150, 110)
    FOOTNOTE = _('Arrows or W A S D: push the cart   stop under the lit '
                 'flag   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Keep the lantern off the ground; stop under each '
                         'lit flag')
        self.flip = 0
        return ok

    def _held(self) -> Optional[int]:
        k = self.keys
        across = (1 if k[key.RIGHT] or k[key.D] else 0) - \
            (1 if k[key.LEFT] or k[key.A] else 0)
        along = (1 if k[key.UP] or k[key.W] else 0) - \
            (1 if k[key.DOWN] or k[key.S] else 0)
        wants = []
        if across:
            wants.append(model.RIGHT if across > 0 else model.LEFT)
        if along:
            wants.append(model.AWAY if along > 0 else model.NEAR)
        if not wants:
            return None
        # both held: one each step, turn about
        self.flip = getattr(self, 'flip', 0) + 1
        return wants[self.flip % len(wants)]

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height)
        T = model.TRACK
        t = run.t
        # a camera behind and above the cart
        eye = (run.x, 8.0, run.z - 12.0)
        lens = self.camera(eye, (0.0, -0.42, 1.0), left, bottom, width,
                           height, fov=62.0, x_right=True)
        # the ground beyond the fence, the yard, its grid and fence
        g = self.layer()
        far = 80.0
        self.face(lens, [(-far, 0, -far), (T + far, 0, -far),
                         (T + far, 0, T + far), (-far, 0, T + far)],
                  (150, 96, 70), g)
        self.face(lens, [(0, 0, 0), (T, 0, 0), (T, 0, T), (0, 0, T)],
                  (206, 160, 104), g)
        for k in range(0, int(T) + 1, 3):
            self.seg(lens, (k, 0, 0), (k, 0, T), 1, (180, 134, 88), g)
            self.seg(lens, (0, 0, k), (T, 0, k), 1, (180, 134, 88), g)
        for (a, b) in (((0, 0), (T, 0)), ((T, 0), (T, T)), ((T, T), (0, T)),
                       ((0, T), (0, 0))):
            self.seg(lens, (a[0], 0.6, a[1]), (b[0], 0.6, b[1]), 3,
                     (110, 70, 50), g)
        # the hold ring under the lit flag
        g = self.layer()
        if run.flag < len(run.course.flags):
            fx, fz = run.course.flags[run.flag]
            ring = [(fx + 0.8 * math.cos(a * math.pi / 12), 0.01,
                     fz + 0.8 * math.sin(a * math.pi / 12))
                    for a in range(24)]
            self.face(lens, ring, (250, 236, 170), g)
            share = min(1.0, run.still / model.HOLD)
            if share > 0:
                pie = [(fx, 0.02, fz)] + [
                    (fx + 0.8 * math.cos(a), 0.02, fz + 0.8 * math.sin(a))
                    for a in [2 * math.pi * share * i / 16
                              for i in range(17)]]
                self.face(lens, pie, (90, 200, 110), g)
        # gusts: dust streaks blowing the way the wind pushes
        gx, gz = run.gust()
        if run.level.gusts:
            for k in range(14):
                u = (k * 2.3 + t * 3.0) % 12.0 - 6.0
                px = run.x + ((k * 3.7) % 16.0 - 8.0) + gx * u
                pz = run.z + ((k * 5.3) % 14.0 - 2.0) + gz * u
                self.seg(lens, (px, 0.5 + k % 3, pz),
                         (px - gx * 1.5, 0.5 + k % 3, pz - gz * 1.5), 1,
                         (255, 230, 200), g)
        # flags and the cart, far ones first
        tip = run.tip()
        hinge = (run.x, DECK, run.z)
        top = (hinge[0] + tip[0], hinge[1] + tip[1], hinge[2] + tip[2])
        things = []
        for k, (fx, fz) in enumerate(run.course.flags):
            things.append((fz, 'flag', k))
        things.append((run.z, 'cart', 0))
        for _depth, what, k in sorted(things, key=lambda th: -th[0]):
            g = self.layer()
            if what == 'flag':
                fx, fz = run.course.flags[k]
                lit = k == run.flag
                done = k < run.flag
                col = (150, 140, 130) if done else FLAGS[k % len(FLAGS)]
                if not lit and not done:
                    col = polish.mix(col, (120, 100, 110), 0.45)
                self.seg(lens, (fx, 0, fz), (fx, 3.2, fz), 2,
                         (240, 240, 240), g)
                self.face(lens, [(fx, 3.2, fz), (fx + 1.1, 2.85, fz),
                                 (fx, 2.5, fz)], col, g)
                continue
            # the pole's shadow, then the cart and the pole
            self.seg(lens, (run.x, 0.02, run.z),
                     (run.x + tip[0], 0.02, run.z + tip[2]), 4,
                     (120, 80, 60), g)
            self.box(lens, run.x - 0.9, 0.25, run.z - 0.6, run.x + 0.9,
                     DECK, run.z + 0.6, (196, 64, 54), g)
            for sx in (-0.6, 0.6):
                for sz in (-0.62, 0.62):
                    self.ball(lens, (run.x + sx, 0.25, run.z + sz), 0.25,
                              (50, 50, 60), g)
            danger = min(1.0, run.lean() / (math.pi / 2))
            self.seg(lens, hinge, top, 5,
                     polish.mix((240, 230, 210), (255, 80, 60), danger), g)
            self.ball(lens, top, 0.32, (255, 226, 150), g, shade=0.1)
            px, pz = run.pushing
            if px or pz:
                for j in range(3):
                    self.ball(lens, (run.x - px * (1.2 + 0.3 * j), 0.06,
                                     run.z - pz * (0.9 + 0.3 * j)),
                              0.05 + 0.02 * j, (176, 136, 96), g)
        self._gauge(run, left, bottom, width, height)
        self._map(run, left, bottom, width, height)
        # the clock along the top
        g = self.layer()
        share = max(0.0, 1.0 - t / run.level.seconds)
        bar_w = width - 40
        self.rect(left + 20, bottom + height - 22, bar_w, 8, (90, 70, 100),
                  g)
        if share > 0.01:
            self.rect(left + 20, bottom + height - 22, bar_w * share, 8,
                      polish.mix((236, 80, 64), (60, 190, 120),
                                 min(1.0, share * 1.6)), g)

    def _gauge(self, run, left, bottom, width, height) -> None:
        """The lean seen from above: the dot is where the lantern is over
        the ground, the rim is where it would touch it."""
        g = self.layer()
        r = max(30.0, min(width, height) * 0.09)
        cx, cy = left + width - r - 18, bottom + height - r - 40
        self.disc((cx, cy), r + 3, (60, 40, 50), g)
        self.disc((cx, cy), r, (40, 32, 44), g)
        self.disc((cx, cy), r * math.sin(math.radians(12)) + 2,
                  (60, 110, 70), g)
        tip, l = run.tip(), run.length()
        dx, dz = tip[0] / l, tip[2] / l
        danger = min(1.0, run.lean() / (math.pi / 2))
        g = self.layer()
        self.line((cx, cy), (cx + dx * r, cy + dz * r), 2, (200, 190, 180),
                  g)
        self.disc((cx + dx * r, cy + dz * r), max(4.0, r * 0.13),
                  polish.mix((120, 240, 150), (255, 70, 60), danger), g)

    def _map(self, run, left, bottom, width, height) -> None:
        """The yard from above: the flags, the cart."""
        g = self.layer()
        side = max(60.0, min(width, height) * 0.18)
        x0, y0 = left + 18, bottom + height - side - 40
        s = side / model.TRACK
        self.rect(x0 - 3, y0 - 3, side + 6, side + 6, (110, 70, 50), g)
        self.rect(x0, y0, side, side, (206, 160, 104), g)
        g = self.layer()
        for k, (fx, fz) in enumerate(run.course.flags):
            col = (150, 140, 130) if k < run.flag else FLAGS[k % len(FLAGS)]
            self.disc((x0 + fx * s, y0 + fz * s),
                      5 if k == run.flag else 3, col, g)
        self.disc((x0 + run.x * s, y0 + run.z * s), 4, (196, 40, 40), g)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   flag %d of %d') % (
            self.rung, self.trial, self.total_trials,
            min(run.flag + 1, len(run.course.flags)), len(run.course.flags))
