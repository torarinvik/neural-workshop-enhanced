# -*- coding: utf-8 -*-
"""Balance on screen: a handcar at dusk with a lantern pole on top.

Hold Left and Right to push the cart; the pole carries a lantern and
leans the other way. A gauge on the cart reads the lean against the
falling point. Flags stand along the track; the one to stop under is
lit, and a ring fills while the cart holds still there. Dust and
rolling tumbleweed show the gusts.

For the agent boundary: ports 0 and 1 push the cart left and right for
one step.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Optional, Tuple

import pyglet
from pyglet.window import key

from .. import balance as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask

FLAGS = ((236, 72, 80), (60, 150, 236), (250, 196, 50), (90, 200, 120),
         (180, 100, 230), (240, 130, 60))
WORLD_H = 12.0
GROUND = 2.0


class Balance(ClockedTask):
    """Every flag in turn, the pole never down."""

    instance: Optional['Balance'] = None

    TITLE = 'Balance'
    TASK_ID = 'balance'
    PREFIX = 'BALANCE'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    FOOTNOTE = _('Left / Right: push the cart   stop under the lit flag   '
                 'Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Keep the pole up; stop under each lit flag')
        return ok

    def _held(self) -> Optional[int]:
        k = self.keys
        if k[key.LEFT] or k[key.A]:
            return model.LEFT
        if k[key.RIGHT] or k[key.D]:
            return model.RIGHT
        return None

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        s = min(width / model.TRACK, height / (WORLD_H + 1.4))
        x0 = left + (width - model.TRACK * s) / 2
        return x0, bottom, s

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    def _build_scenery(self) -> None:
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.TRACK * s, WORLD_H * s
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12, (60, 40, 70),
                    radius=14, shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        polish.gradient(out, batch, x0, y0, W, H, (250, 160, 90),
                        (70, 50, 120), bands=24, group=g0)
        sun = self._at(model.TRACK * 0.7, 4.2)
        polish.glow(out, batch, sun[0], sun[1], 4.0 * s, (255, 200, 120),
                    strength=110, group=g0)
        out.append(pyglet.shapes.Circle(sun[0], sun[1], 1.4 * s,
                                        color=(255, 214, 140), batch=batch,
                                        group=g0))
        draw = random.Random(len(self.run.course.flags) * 7 +
                             self.run.course.gust_seed % 97)
        # Mesas on the horizon.
        x = 0.0
        while x < model.TRACK:
            w = min(draw.uniform(2.5, 6.0), model.TRACK - x)
            h = draw.uniform(1.0, 3.2)
            px, py = self._at(x, GROUND)
            out.append(pyglet.shapes.Polygon(
                (px, py), (px + w * 0.15 * s, py + h * s),
                (px + w * 0.85 * s, py + h * s), (px + w * s, py),
                color=(120, 70, 90), batch=batch, group=g0))
            x += w + draw.uniform(0.5, 3.0)
        gx, gy = self._at(0, 0)
        polish.gradient(out, batch, gx, gy, W, GROUND * s, (150, 96, 60),
                        (196, 132, 80), bands=6, group=g1)
        # Rails and sleepers.
        ry = y0 + (GROUND - 0.35) * s
        for k in range(int(model.TRACK * 1.5)):
            sx = x0 + k * s / 1.5
            out.append(pyglet.shapes.Rectangle(sx, ry - 0.2 * s, 0.3 * s,
                                               0.35 * s, color=(90, 60, 40),
                                               batch=batch, group=g1))
        out.append(pyglet.shapes.Rectangle(x0, ry, W, 0.12 * s,
                                           color=(200, 200, 210), batch=batch,
                                           group=g1))
        for bx in (0.3, model.TRACK - 0.3):
            px, py = self._at(bx, GROUND - 0.4)
            out.append(pyglet.shapes.Rectangle(px - 0.3 * s, py, 0.6 * s,
                                               0.9 * s, color=(200, 60, 50),
                                               batch=batch, group=g1))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        course = run.course
        self._scenery_fresh(self._frame())
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        t = run.t
        # Flags.
        for k, fx in enumerate(course.flags):
            px, py = self._at(fx, GROUND)
            hue = FLAGS[k % len(FLAGS)]
            done = k < run.flag
            now = k == run.flag
            d.append(pyglet.shapes.Line(px, py, px, py + 3.6 * s, thickness=2,
                                        color=(230, 220, 210), batch=batch,
                                        group=body))
            wave = math.sin(t * 4 + k) * 0.15 * s
            d.append(pyglet.shapes.Triangle(
                px, py + 3.6 * s, px, py + 2.8 * s,
                px + 1.1 * s, py + 3.2 * s + wave,
                color=(90, 210, 120) if done else hue, batch=batch,
                group=text))
            if now:
                polish.glow(d, batch, px, py + 3.2 * s, 1.8 * s, hue,
                            strength=110, group=card)
                d.append(pyglet.shapes.Box(px - 0.8 * s, py - 0.2 * s,
                                           1.6 * s, 0.3 * s, thickness=2,
                                           color=hue, batch=batch,
                                           group=text))
                if run.still > 0:
                    d.append(pyglet.shapes.Arc(
                        px, py + 3.2 * s, 0.9 * s, thickness=3,
                        angle=360 * run.still / model.HOLD, start_angle=90,
                        color=(120, 240, 150), batch=batch, group=top))
            self._text(str(k + 1), px - 0.4 * s, py + 3.6 * s,
                       max(8.0, 0.5 * s), bold=True,
                       colour=(255, 255, 255, 230))
        # Gusts: dust streaks and a tumbleweed.
        gust = run.gust()
        if run.level.gusts:
            for k in range(10):
                gx = (k * 3.3 + t * gust * 6.0) % model.TRACK
                gy = GROUND + 0.5 + (k * 1.7) % 7.0
                px, py = self._at(gx, gy)
                d.append(pyglet.shapes.Line(
                    px, py, px - math.copysign(1.2, gust) * s * min(
                        1.0, abs(gust)), py, thickness=1,
                    color=(255, 230, 200, 120), batch=batch, group=card))
            wx = (t * gust * 2.5 + 7.0) % model.TRACK
            px, py = self._at(wx, GROUND + 0.4)
            d.append(pyglet.shapes.Arc(px, py, 0.4 * s, thickness=2,
                                       color=(150, 110, 60), batch=batch,
                                       group=text))
        # The cart.
        cx, cy = self._at(run.x, GROUND)
        d.append(pyglet.shapes.RoundedRectangle(
            cx - 1.1 * s, cy, 2.2 * s, 0.8 * s, radius=0.15 * s,
            color=(196, 64, 54), batch=batch, group=body))
        d.append(pyglet.shapes.Rectangle(cx - 1.1 * s, cy + 0.6 * s, 2.2 * s,
                                         0.12 * s, color=(250, 206, 80),
                                         batch=batch, group=text))
        spin = -run.x / 0.3
        for side in (-0.65, 0.65):
            wx, wy = cx + side * s, cy
            d.append(pyglet.shapes.Circle(wx, wy, 0.32 * s,
                                          color=(40, 40, 50), batch=batch,
                                          group=text))
            d.append(pyglet.shapes.Line(
                wx, wy, wx + math.cos(spin) * 0.28 * s,
                wy + math.sin(spin) * 0.28 * s, thickness=2,
                color=(220, 220, 230), batch=batch, group=top))
        if run.pushing:
            for k in range(3):
                px = cx - run.pushing * (1.3 + 0.3 * k) * s
                d.append(pyglet.shapes.Circle(
                    px, cy + 0.1 * s, (0.15 + 0.06 * k) * s,
                    color=(230, 200, 160, 160 - 40 * k), batch=batch,
                    group=text))
        # The pole and its lantern.
        l = run.length()
        hx, hy = cx, cy + 0.8 * s
        tx = hx + math.sin(run.theta) * l * 1.7 * s
        ty = hy + math.cos(run.theta) * l * 1.7 * s
        danger = abs(run.theta) / model.FALLEN
        d.append(pyglet.shapes.Line(hx, hy, tx, ty,
                                    thickness=max(3.0, 0.16 * s),
                                    color=polish.mix((240, 230, 210),
                                                     (255, 80, 60),
                                                     min(1.0, danger)),
                                    batch=batch, group=text))
        for k in range(1, 4):
            f = k / 4
            d.append(pyglet.shapes.Circle(hx + (tx - hx) * f,
                                          hy + (ty - hy) * f, 0.1 * s,
                                          color=(200, 60, 50), batch=batch,
                                          group=top))
        polish.glow(d, batch, tx, ty, 1.6 * s, (255, 210, 120),
                    strength=120, group=card)
        d.append(pyglet.shapes.Circle(tx, ty, 0.32 * s, color=(255, 226, 150),
                                      batch=batch, group=top))
        # The lean gauge on the cart.
        gx, gy = cx, cy + 0.4 * s
        d.append(pyglet.shapes.Sector(gx, gy, 0.55 * s, angle=70,
                                      start_angle=55, color=(40, 30, 40),
                                      batch=batch, group=text))
        a = math.radians(90) - run.theta * (35 / 35)
        d.append(pyglet.shapes.Line(
            gx, gy, gx + math.cos(a) * 0.5 * s, gy + math.sin(a) * 0.5 * s,
            thickness=2, color=polish.mix((120, 240, 150), (255, 70, 60),
                                          min(1.0, danger * 1.3)),
            batch=batch, group=top))
        # The clock along the top.
        top_y = y0 + (WORLD_H + 0.3) * s
        share = max(0.0, 1.0 - t / run.level.seconds)
        W = model.TRACK * s
        polish.rounded(d, batch, x0, top_y, W, 0.6 * s, (200, 190, 210),
                       radius=0.3 * s, group=card)
        if share > 0.02:
            polish.rounded(d, batch, x0, top_y, W * share, 0.6 * s,
                           polish.mix((236, 80, 64), (60, 190, 120),
                                      min(1.0, share * 1.6)),
                           radius=0.3 * s, group=body)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   flag %d of %d') % (
            self.rung, self.trial, self.total_trials,
            min(run.flag + 1, len(run.course.flags)), len(run.course.flags))
