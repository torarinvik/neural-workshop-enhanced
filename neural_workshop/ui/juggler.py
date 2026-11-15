# -*- coding: utf-8 -*-
"""Juggler on screen: a striped big top, spotlights, a unicyclist.

Hold Left and Right to ride the unicycle and its tray. Every ball
casts a shadow on the sawdust that tightens as it falls, so where a
ball will land is written on the floor. Heavy balls are deep and
metallic and fly low; light ones are pale and fly high. From rung 13
bunting and drifting confetti show the draught.

For the agent boundary: ports 0 and 1 push the tray left and right for
one step; sending nothing brakes.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import pyglet
from pyglet.window import key

from .. import juggler as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask

HUES = ((236, 70, 90), (60, 150, 236), (250, 200, 50), (90, 200, 120),
        (180, 100, 230))
TENT_A = (196, 44, 52)
TENT_B = (248, 236, 214)
SAWDUST = (214, 170, 110)


class Juggler(ClockedTask):
    """Keep every ball in the air."""

    instance: Optional['Juggler'] = None

    TITLE = 'Juggler'
    TASK_ID = 'juggler'
    PREFIX = 'JUGGLER'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    FOOTNOTE = _('Left / Right: ride the tray under the balls   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Keep every ball in the air')
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
        s = min(width / model.WORLD_W, height / (model.WORLD_H + 1.6))
        x0 = left + (width - model.WORLD_W * s) / 2
        return x0, bottom, s

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    def _build_scenery(self) -> None:
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.WORLD_W * s, model.WORLD_H * s
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12, (90, 30, 40),
                    radius=14, shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        stripes = 16
        for k in range(stripes):
            sx = x0 + k * W / stripes
            hue = TENT_A if k % 2 == 0 else TENT_B
            polish.gradient(out, batch, sx, y0 + 1.2 * s, W / stripes + 0.5,
                            H - 1.2 * s, polish.darker(hue, 0.35),
                            polish.darker(hue, 0.05), bands=10, group=g0)
        # The canvas roof's scallops and the ring floor.
        for k in range(stripes):
            cx, cy = self._at((k + 0.5) * model.WORLD_W / stripes,
                              model.WORLD_H)
            out.append(pyglet.shapes.Sector(
                cx, cy, W / stripes / 2, angle=180, start_angle=180,
                color=TENT_A if k % 2 else (250, 200, 60), batch=batch,
                group=g1))
        polish.gradient(out, batch, x0, y0, W, 1.4 * s,
                        polish.darker(SAWDUST, 0.15), SAWDUST, bands=5,
                        group=g1)
        out.append(pyglet.shapes.Rectangle(x0, y0 + 1.35 * s, W, 0.18 * s,
                                           color=(250, 214, 90), batch=batch,
                                           group=g1))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        level = run.level
        self._scenery_fresh(self._frame())
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        t = run.t
        W = model.WORLD_W * s
        # Spotlights that sway.
        for k, (cx_w, hue) in enumerate(((8.0, (255, 240, 200)),
                                         (24.0, (200, 220, 255)))):
            sway = math.sin(t * 0.5 + k * 2.0) * 2.0
            px, py = self._at(cx_w + sway, 10.0)
            polish.glow(d, batch, px, py, 5.0 * s, hue, strength=50,
                        group=card)
        # Draught: bunting and confetti.
        wind = run.draught()
        if level.draught:
            for k in range(12):
                bx, by = self._at(1.5 + k * 2.6, model.WORLD_H - 2.0 -
                                  0.5 * math.sin(k * 0.8))
                lean = wind * 0.8
                d.append(pyglet.shapes.Triangle(
                    bx - 0.6 * s, by, bx + 0.6 * s, by,
                    bx + lean * s, by - 1.1 * s,
                    color=HUES[k % len(HUES)], batch=batch, group=body))
            for k in range(24):
                fx = (k * 3.7 + t * wind * 3.0) % model.WORLD_W
                fy = (k * 5.1 - t * 1.2) % (model.WORLD_H - 3) + 2
                px, py = self._at(fx, fy)
                d.append(pyglet.shapes.Rectangle(
                    px, py, 0.25 * s, 0.15 * s,
                    color=HUES[k % len(HUES)] + (180,), batch=batch,
                    group=card))
        # Shadows on the floor, tightening as each ball falls.
        for k, b in enumerate(run.balls):
            if not b.live:
                continue
            h = max(0.0, b.y - model.TRAY_Y) / model.WORLD_H
            px, py = self._at(b.x, 0.7)
            d.append(pyglet.shapes.Ellipse(
                px, py, (0.5 + 1.6 * h) * s, (0.18 + 0.3 * h) * s,
                color=(60, 30, 20, int(170 * (1 - h) + 30)), batch=batch,
                group=body))
        # The cart: a painted body on two wheels, a springy top.
        tx, ty = self._at(run.x, model.TRAY_Y)
        half = level.tray / 2 * s
        spin = -run.x / 0.4
        body_y = y0 + 0.55 * s
        d.append(pyglet.shapes.RoundedRectangle(
            tx - half * 0.9, body_y, half * 1.8, ty - body_y - 0.1 * s,
            radius=0.2 * s, color=(60, 80, 170), batch=batch, group=body))
        for k in range(4):
            d.append(pyglet.shapes.Circle(
                tx - half * 0.6 + k * half * 0.4, (body_y + ty) / 2,
                0.12 * s, color=(250, 214, 90), batch=batch, group=text))
        for side in (-0.6, 0.6):
            wx, wy = tx + side * half, y0 + 0.45 * s
            d.append(pyglet.shapes.Circle(wx, wy, 0.42 * s,
                                          color=(40, 40, 50), batch=batch,
                                          group=text))
            for k in range(2):
                a = spin + k * math.pi / 2
                d.append(pyglet.shapes.Line(
                    wx - math.cos(a) * 0.36 * s, wy - math.sin(a) * 0.36 * s,
                    wx + math.cos(a) * 0.36 * s, wy + math.sin(a) * 0.36 * s,
                    thickness=1, color=(220, 220, 230), batch=batch,
                    group=top))
        d.append(pyglet.shapes.Rectangle(tx - half, ty - 0.12 * s, half * 2,
                                         0.24 * s, color=(250, 206, 70),
                                         batch=batch, group=text))
        d.append(pyglet.shapes.Rectangle(tx - half, ty + 0.08 * s, half * 2,
                                         0.06 * s, color=(255, 240, 170),
                                         batch=batch, group=top))
        for when, fx in run.flashes:
            age = t - when
            if age < 0.4:
                px, py = self._at(fx, model.TRAY_Y + 0.3)
                d.append(pyglet.shapes.Arc(px, py, (0.5 + age * 4) * s,
                                           thickness=2,
                                           color=(255, 250, 200,
                                                  int(255 * (1 - age / 0.4))),
                                           batch=batch, group=top))
        # Balls: trails, then the ball with its shine.
        for k, b in enumerate(run.balls):
            if not b.live:
                px, py = self._at(run.act.drops[k][1], model.WORLD_H - 0.6)
                due = run.act.drops[k][0] - t
                d.append(pyglet.shapes.Arc(px, py, 0.7 * s, thickness=2,
                                           angle=360 * max(0.0, min(1.0,
                                                                    due / 3)),
                                           color=HUES[k % len(HUES)],
                                           batch=batch, group=top))
                continue
            hue = HUES[k % len(HUES)]
            if b.weight > 1.1:
                hue = polish.mix(hue, (40, 40, 60), 0.45)
            elif b.weight < 0.9:
                hue = polish.mix(hue, (255, 255, 255), 0.45)
            for j, (qx, qy) in enumerate(b.trail):
                px, py = self._at(qx, qy)
                d.append(pyglet.shapes.Circle(px, py, (0.15 + 0.03 * j) * s,
                                              color=hue + (30 + 18 * j,),
                                              batch=batch, group=card))
            px, py = self._at(b.x, b.y)
            r = model.RADIUS * s * (1.15 if b.weight > 1.1 else 1.0)
            polish.disc(d, batch, px, py, r, hue, group=text)
        # Along the top: the act's clock.
        top_y = y0 + (model.WORLD_H + 0.4) * s
        share = max(0.0, 1.0 - t / level.seconds)
        polish.rounded(d, batch, x0, top_y, W, 0.7 * s, (200, 190, 200),
                       radius=0.35 * s, group=card)
        if share < 0.98:
            polish.rounded(d, batch, x0, top_y, W * (1 - share), 0.7 * s,
                           (250, 200, 60), radius=0.35 * s, group=body)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        left = max(0, int(run.level.seconds - run.t))
        return _('rung %d  %d/%d   %d balls   %d s to go') % (
            self.rung, self.trial, self.total_trials, len(run.balls), left)
