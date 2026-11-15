# -*- coding: utf-8 -*-
"""Lander on screen: the ground, the pad, the craft, its instruments.

Up fires the engine; Left and Right turn the craft. A flame shows while
it fires. Along the top: speed down and across, tilt, fuel and -- from
rung 10 -- a wind arrow; the limits for a landing sit beside them. The
pad is the bright stretch of ground.

For the agent boundary: one port a frame -- 0 fire, 1 turn left,
2 turn right, 3 fire and turn left, 4 fire and turn right; no port is
coasting.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import lander as model, state
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

SKY = (16, 18, 30)
GROUND = (110, 104, 96)
PAD = (240, 200, 60)
CRAFT = (226, 228, 236)
FLAME = (255, 140, 40)
INK = (230, 232, 240, 255)


class Lander(RungTask):
    """Land gently, upright, on the pad."""

    instance: Optional['Lander'] = None

    TITLE = 'Lander'
    TASK_ID = 'lander'
    PREFIX = 'LANDER'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    FOOTNOTE = _('Up: fire   Left / Right: turn   Esc: menu')

    def __init__(self) -> None:
        self.craft: Optional[model.Craft] = None
        self.control: Optional[int] = None
        self.last_tick = 0.0
        self.keys = key.KeyStateHandler()
        super().__init__()
        state.window.push_handlers(self.keys)

    def close(self) -> None:
        if type(self).instance is self:
            state.window.remove_handlers(self.keys)
        super().close()

    def _clear_trial(self) -> None:
        self.craft = None

    def _deal(self) -> bool:
        self.craft = model.Craft(model.deal(self.rung, rng=self.rng))
        self.last_tick = self.clock()
        self.control = None
        self.message = _('Land on the pad: gently, upright')
        return True

    def steer(self, port: int) -> None:
        if 0 <= port <= model.THRUST_RIGHT:
            self.control = port

    def _held(self) -> Optional[int]:
        fire = self.keys[key.UP] or self.keys[key.W]
        left = self.keys[key.LEFT] or self.keys[key.A]
        right = self.keys[key.RIGHT] or self.keys[key.D]
        turn = (1 if left else 0) - (1 if right else 0)
        if fire:
            return {0: model.THRUST, 1: model.THRUST_LEFT,
                    -1: model.THRUST_RIGHT}[turn]
        return {0: None, 1: model.LEFT, -1: model.RIGHT}[turn]

    def _tick(self) -> None:
        now = self.clock()
        dt = max(0.0, min(0.1, now - self.last_tick))
        self.last_tick = now
        control = self.control if self.control is not None else \
            self._held()
        self.control = None
        craft = self.craft
        # Small steps, so a slow frame does not tunnel through the ground.
        steps = max(1, int(math.ceil(dt / (1 / 120.0))))
        for _s in range(steps):
            craft.step(dt / steps, control)
        if craft.result is not None:
            self._judge(*craft.result)
        else:
            self._redraw()

    def _draw(self, left, bottom, width, height) -> None:
        craft = self.craft
        f = craft.flight
        level = f.level
        scale = min(width / model.WORLD_W, height / model.WORLD_H)
        x0 = left + (width - model.WORLD_W * scale) / 2

        def at(x, y):
            return x0 + x * scale, bottom + y * scale
        self._box(x0, bottom, model.WORLD_W * scale, model.WORLD_H * scale,
                  SKY)
        pts = [at(x, y) for x, y in f.ground]
        poly = [at(0, 0)] + pts + [at(model.WORLD_W, 0)]
        self.drawn.append(pyglet.shapes.Polygon(
            *poly, color=GROUND, batch=self.batch, group=self.body_group))
        pc = model.pad_centre(f, craft.t)
        px, py = at(pc - level.pad / 2, f.pad_y)
        self._box(px, py - scale * 0.6, level.pad * scale, scale * 0.6, PAD,
                  group=self.text_group)
        # The craft: a body, two legs, and a flame while firing.
        ca, sa = math.cos(craft.angle), math.sin(craft.angle)

        def body(dx, dy):
            return at(craft.x + dx * ca - dy * sa, craft.y + dx * sa + dy * ca)
        hull = [body(-model.HALF_W * 0.7, 0.8), body(model.HALF_W * 0.7, 0.8),
                body(model.HALF_W * 0.5, model.HIGH),
                body(-model.HALF_W * 0.5, model.HIGH)]
        self.drawn.append(pyglet.shapes.Polygon(
            *hull, color=CRAFT, batch=self.batch, group=self.top_group))
        for side in (-1, 1):
            a, b = body(side * model.HALF_W * 0.5, 0.9), \
                body(side * model.HALF_W, 0.0)
            self.drawn.append(pyglet.shapes.Line(
                a[0], a[1], b[0], b[1], thickness=max(1.5, scale * 0.25),
                color=CRAFT, batch=self.batch, group=self.top_group))
        if craft.firing:
            flame = [body(-0.5, 0.8), body(0.5, 0.8), body(0.0, -1.6)]
            self.drawn.append(pyglet.shapes.Polygon(
                *flame, color=FLAME, batch=self.batch, group=self.top_group))
        # Instruments.
        size = calc_fontsize(12)
        rel = craft.vx - model.pad_speed(f, craft.t)
        words = [_('down %.1f / %.1f') % (-craft.vy, level.max_down),
                 _('across %.1f / %.1f') % (abs(rel), level.max_across),
                 _('tilt %d / %d') % (round(math.degrees(craft.angle)),
                                      round(math.degrees(level.max_tilt)))]
        words.append(_('fuel %.1f s') % craft.fuel if craft.fuel is not None
                     else _('fuel unlimited'))
        tx, ty = at(1.5, model.WORLD_H - 2)
        for i, w in enumerate(words):
            self._text(w, tx, ty - i * size * 1.8, size, anchor='left',
                       colour=INK, group=self.top_group)
        if level.wind:
            wind = model.wind_at(f, craft.t)
            cx, cy = at(model.WORLD_W - 10, model.WORLD_H - 4)
            length = wind * scale * 14
            self.drawn.append(pyglet.shapes.Line(
                cx, cy, cx + length, cy, thickness=3, color=(140, 200, 255),
                batch=self.batch, group=self.top_group))
            self._text(_('wind'), cx, cy - size * 1.4, size, colour=INK,
                       group=self.top_group)

    def _facts(self) -> str:
        if self.craft is None:
            return ''
        return _('rung %d  %d/%d   %d s') % (self.rung, self.trial,
                                             self.total_trials,
                                             int(self.craft.t))
