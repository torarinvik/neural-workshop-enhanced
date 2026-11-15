# -*- coding: utf-8 -*-
"""Glider on screen: a paper glider in a desert canyon at sunset.

Hold to climb, let go to sink. Sandstone pillars slide in with a gap
in each; the glider tips its nose with its climb, leaves a dotted trail,
and gusts show as streaks of dust. Dots along the top count the walls.

For the agent boundary: port 0 lifts, for the step it is sent in --
send it every step to keep climbing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Optional

import pyglet
from pyglet.window import key

from .. import glider as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask


class Glider(ClockedTask):
    """Thread the glider through every gap."""

    instance: Optional['Glider'] = None

    TITLE = 'Glider'
    TASK_ID = 'glider'
    PREFIX = 'GLIDER'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    FOOTNOTE = _('hold Space (or Up) to climb, let go to sink   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Thread every gap')
        return ok

    def _held(self) -> Optional[int]:
        k = self.keys
        return model.UP if (k[key.SPACE] or k[key.UP] or k[key.W]) else None

    def _frame(self):
        left, bottom, width, height = self._area()
        s = min(width / model.W, height / model.H)
        return left + (width - model.W * s) / 2, bottom + (
            height - model.H * s) / 2, s

    def _build_scenery(self) -> None:
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        W, H = model.W * s, model.H * s
        g0 = pyglet.graphics.Group(order=-14)
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12,
                    (60, 30, 30), radius=14, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        polish.gradient(out, batch, x0, y0, W, H, (250, 170, 100),
                        (90, 60, 140), bands=24, group=g0)
        polish.glow(out, batch, x0 + W * 0.8, y0 + H * 0.3, H * 0.3,
                    (255, 220, 150), strength=90, group=g0)
        draw = random.Random(5)
        x = 0.0
        while x < model.W:
            w = draw.uniform(8, 16)
            h = draw.uniform(8, 20)
            end = min(model.W, x + w)
            out.append(pyglet.shapes.Polygon(
                (x0 + x * s, y0),
                (x0 + min(end, x + w * 0.2) * s, y0 + h * s),
                (x0 + min(end, x + w * 0.8) * s, y0 + h * s),
                (x0 + end * s, y0),
                color=(150, 80, 80), batch=batch, group=g0))
            x += w * 0.8

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        x0, y0, s = self._frame()
        self._scenery_fresh(self._frame())
        d, batch = self.drawn, self.batch
        level = run.level
        W, H = model.W * s, model.H * s
        clip = pyglet.graphics.Group(order=2)
        for i in range(len(run.course.walls)):
            wx, c = run.wall(i)
            if wx < -model.WALL or wx > model.W + model.WALL:
                continue
            gx = x0 + (wx - model.WALL / 2) * s
            gw = model.WALL * s
            lo = (c - level.gap / 2) * s
            hi = (c + level.gap / 2) * s
            left_edge = max(x0, gx)
            right_edge = min(x0 + W, gx + gw)
            if right_edge <= left_edge:
                continue
            for y, h in ((y0, lo), (y0 + hi, H - hi)):
                d.append(pyglet.shapes.Rectangle(
                    left_edge, y, right_edge - left_edge, h,
                    color=(200, 110, 70), batch=batch, group=clip))
                for k in range(int(h / (2.5 * s)) + 1):
                    sy = y + k * 2.5 * s
                    if sy < y + h:
                        d.append(pyglet.shapes.Line(
                            left_edge, sy, right_edge, sy, thickness=1,
                            color=(170, 86, 56), batch=batch,
                            group=self.body_group))
            for edge_y in (y0 + lo, y0 + hi):
                d.append(pyglet.shapes.Rectangle(
                    left_edge - 2, edge_y - 3, right_edge - left_edge + 4,
                    6, color=(120, 60, 40), batch=batch,
                    group=self.body_group))
        # Gusts as dust streaks.
        gust = run.gust()
        if level.gust:
            for k in range(12):
                gx = (k * 9.0 - run.t * 30) % model.W
                gy = (k * 13.0 + run.t * gust * 2) % model.H
                d.append(pyglet.shapes.Line(
                    x0 + gx * s, y0 + gy * s, x0 + (gx + 4) * s,
                    y0 + (gy + gust * 0.12) * s, thickness=1,
                    color=(255, 240, 210, 110), batch=batch,
                    group=self.body_group))
        # Trail and glider.
        for tt, ty in run.trail:
            tx = model.X - (run.t - tt) * level.speed
            if tx > 0:
                d.append(pyglet.shapes.Circle(x0 + tx * s, y0 + ty * s,
                                              0.3 * s,
                                              color=(255, 255, 255, 140),
                                              batch=batch,
                                              group=self.text_group))
        gx, gy = x0 + model.X * s, y0 + run.y * s
        tilt = max(-0.6, min(0.6, run.vy / 40.0))
        c, si = math.cos(tilt), math.sin(tilt)

        def pt(u, v):
            return gx + (u * c - v * si) * s, gy + (u * si + v * c) * s
        d.append(pyglet.shapes.Triangle(*pt(3.0, 0), *pt(-2.4, 1.6),
                                        *pt(-1.4, 0), color=(250, 250, 255),
                                        batch=batch, group=self.top_group))
        d.append(pyglet.shapes.Triangle(*pt(3.0, 0), *pt(-2.4, -1.4),
                                        *pt(-1.4, 0), color=(200, 210, 240),
                                        batch=batch, group=self.top_group))
        if run.lifting:
            polish.glow(d, batch, *pt(-2.6, 0), 1.6 * s, (255, 230, 150),
                        strength=90, group=self.text_group)
        # Walls passed, along the top.
        n = len(run.course.walls)
        for k in range(n):
            cx = x0 + W / 2 + (k - (n - 1) / 2) * 2.6 * s
            d.append(pyglet.shapes.Circle(
                cx, y0 + H - 2 * s, 0.8 * s,
                color=(120, 230, 150) if k < run.passed else
                (255, 255, 255, 120), batch=batch, group=self.top_group))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   wall %d of %d') % (
            self.rung, self.trial, self.total_trials,
            min(self.run.passed + 1, len(self.run.course.walls)),
            len(self.run.course.walls))
