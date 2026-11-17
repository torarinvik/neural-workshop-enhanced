# -*- coding: utf-8 -*-
"""Catch on screen: a court in perspective, a thrower, and baskets.

The court runs away from the player under an evening sky; the thrower
stands at the far end. Balls fly in true perspective -- smaller the
farther -- with a shadow beneath them on the low rungs. The baskets
stand in the near part of the court: move one with the mouse (it runs
to the spot under the pointer) or the arrow keys / WASD. On the
two-basket rungs, red is on the keys and blue on the mouse.

For the agent boundary: ports 0-3 move the first basket left, right,
nearer and farther for one step; ports 4-7 the second.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import catch as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .lens import Lens
from .pointer import Pointer
from .tones import Tones, patch

BASKETS = ((226, 72, 64), (64, 132, 236))
SINGLE = (238, 168, 52)
FOG_RGB = (150, 160, 190)


class Catch(Pointer, Tones, ClockedTask):
    """Be under every ball when it comes down."""

    instance: Optional['Catch'] = None

    TITLE = 'Catch'
    TASK_ID = 'catch'
    PREFIX = 'CATCH'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    FOOTNOTE = _('Mouse or arrows / WASD: move the basket   Esc: menu')

    def __init__(self) -> None:
        self.last_pointer = None
        self.lens = None
        super().__init__()

    def _deal(self) -> bool:
        ok = super()._deal()
        level = self.run.level
        self.message = (_('Red basket on the keys, blue on the mouse -- '
                          'catch your own colour') if level.two else
                        _('Be under each ball when it comes down'))
        self.last_pointer = self.pointer
        self._tones_start(model.sounds(self.run.court),
                          [patch(n, k + 1) for k, n in
                           enumerate(model.PATCHES)],
                          self.run.court.balls[-1].t0 + 4.0)
        return ok

    # --- controls ---------------------------------------------------------------

    def _held(self):
        k = self.keys
        on = set()
        if k[key.LEFT] or k[key.A]:
            on.add(model.LEFT)
        if k[key.RIGHT] or k[key.D]:
            on.add(model.RIGHT)
        if k[key.UP] or k[key.W]:
            on.add(model.FAR)
        if k[key.DOWN] or k[key.S]:
            on.add(model.NEAR)
        return on or None

    def _tick(self) -> None:
        run = self.run
        if run is not None and self.lens is not None:
            b = run.mouse_basket()
            if self.pointer != self.last_pointer and self.pointer:
                spot = self.lens.on_floor(*self.pointer, y=0.0)
                if spot is not None:
                    run.aim[b] = spot
            self.last_pointer = self.pointer
            held = self._held()
            if held and not run.level.two:
                run.aim[0] = None
        super()._tick()

    # --- drawing ------------------------------------------------------------------

    def _camera(self, left, bottom, width, height) -> Lens:
        run = self.run
        swing = math.radians(run.level.swing) * math.sin(0.3 * run.t)
        pivot = (0.0, 0.0, 14.0)
        back, high = 26.0, 12.0
        eye = (pivot[0] - math.sin(swing) * back, high,
               pivot[2] - math.cos(swing) * back)
        H, L = model.HALF, model.LONG
        # Fitted with the swing at its widest, so the view does not breathe.
        wide = math.radians(run.level.swing)
        frame = []
        for a in {-wide, wide, 0.0}:
            e = (pivot[0] - math.sin(a) * back, high,
                 pivot[2] - math.cos(a) * back)
            probe = Lens(e, (0.0, 0.0, 19.0), 1.0, 0.0, 0.0,
                         x_right=True)
            frame += [probe.see(p) and p for p in
                      ((-H, 0, 0), (H, 0, 0), (-H, 0, L), (H, 0, L),
                       (0, 10.5, L * 0.55), (0, 3.0, L + 1))]
        frame = [p for p in frame if p]
        lens = Lens(eye, (0.0, 0.0, 19.0), 1.0, 0.0, 0.0, x_right=True)
        return lens.fit(frame, left, bottom, width, height)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        d, batch = self.drawn, self.batch
        lens = self.lens = self._camera(left, bottom, width, height)
        level = run.level
        g_sky = pyglet.graphics.Group(order=-14)
        g_floor = pyglet.graphics.Group(order=-13)
        g_line = pyglet.graphics.Group(order=-12)
        polish.card(d, batch, left - 4, bottom - 4, width + 8, height + 8,
                    (40, 40, 70), radius=14, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        polish.gradient(d, batch, left, bottom, width, height,
                        (250, 190, 140), (70, 80, 150), bands=22,
                        group=g_sky)
        H, L = model.HALF, model.LONG

        def flat(x, z, y=0.0):
            p = lens.see((x, y, z))
            return (p[0], p[1]) if p else None

        def poly(points, colour, group):
            pts = [q for q in points if q is not None]
            if len(pts) >= 3:
                d.append(pyglet.shapes.Polygon(*pts, color=colour,
                                               batch=batch, group=group))

        # The court, in strips so the far end can fade.
        strips = 12
        for k in range(strips):
            z0, z1 = L * k / strips, L * (k + 1) / strips
            shade = polish.mix((96, 150, 96), (70, 112, 80), k / strips)
            if level.fog and z1 > model.FOG:
                shade = polish.mix(shade, FOG_RGB, min(1.0, (z1 - model.FOG)
                                                       / 6.0))
            poly([flat(-H, z0), flat(H, z0), flat(H, z1), flat(-H, z1)],
                 shade, g_floor)
        for z in (model.ZONE[3], L / 2):
            a, b = flat(-H, z), flat(H, z)
            if a and b:
                d.append(pyglet.shapes.Line(*a, *b, thickness=2,
                                            color=(235, 240, 225, 160),
                                            batch=batch, group=g_line))
        for x in (-H, H):
            a, b = flat(x, 0.0), flat(x, L)
            if a and b:
                d.append(pyglet.shapes.Line(*a, *b, thickness=3,
                                            color=(235, 240, 225),
                                            batch=batch, group=g_line))
        if level.walls:
            for x in (-H, H):
                poly([flat(x, 0.0), flat(x, L), flat(x, L, 1.6),
                      flat(x, 0.0, 1.6)], (150, 120, 100), g_line)
        x0z, x1z, z0z, z1z = model.ZONE
        for a, b in (((x0z, z0z), (x1z, z0z)), ((x1z, z0z), (x1z, z1z)),
                     ((x1z, z1z), (x0z, z1z)), ((x0z, z1z), (x0z, z0z))):
            pa, pb = flat(*a), flat(*b)
            if pa and pb:
                d.append(pyglet.shapes.Line(*pa, *pb, thickness=1,
                                            color=(255, 255, 255, 90),
                                            batch=batch, group=g_line))
        # Everything with depth, far first.
        things = []
        if not level.fog:
            things.append((L + 1, 'thrower', None))
        for k in run.in_air():
            ball = run.court.balls[k]
            things.append((model.where(ball, run.t, level.walls)[2], 'ball',
                           k))
        for k, ball in enumerate(run.court.balls):
            fate = run.fate[k]
            landed = ball.t0 + ball.flight
            if fate is not None and run.t - landed < 0.7:
                things.append((ball.land[1], 'landed', k))
        for b, basket in enumerate(run.baskets):
            things.append((basket[1], 'basket', b))
        if level.fog:
            things.append((model.FOG, 'fog', None))
        things.sort(key=lambda q: -q[0])
        order = 0
        for _z, kind, k in things:
            order += 1
            g = pyglet.graphics.Group(order=order)
            if kind == 'thrower':
                self._thrower(lens, g)
            elif kind == 'basket':
                self._basket(lens, k, g)
            elif kind == 'fog':
                for k in range(4):
                    y0, y1 = 2.5 * k, 2.5 * (k + 1)
                    poly([flat(-H, model.FOG, y0), flat(H, model.FOG, y0),
                          flat(H, model.FOG, y1), flat(-H, model.FOG, y1)],
                         FOG_RGB + (int(250 - 40 * k),), g)
            elif kind == 'ball':
                self._ball(lens, k, g)
            else:
                self._landed(lens, k, g)
        # The tally.
        y = bottom + height - 22
        n = len(run.court.balls)
        for k in range(n):
            x = left + 20 + k * 22
            fate = run.fate[k]
            colour = ((90, 210, 120) if fate else (230, 70, 60)
                      if fate is False else (255, 255, 255, 90))
            d.append(pyglet.shapes.Circle(x, y, 7, color=colour, batch=batch,
                                          group=pyglet.graphics.Group(
                                              order=201)))

    def _thrower(self, lens, g) -> None:
        d, batch = self.drawn, self.batch
        base = lens.see((0.0, 0.0, model.LONG + 1))
        head = lens.see((0.0, 2.6, model.LONG + 1))
        if not base or not head:
            return
        w = lens.size(0.5, base[2])
        d.append(pyglet.shapes.Line(base[0], base[1], head[0], head[1],
                                    thickness=max(2.0, w), color=(60, 60, 90),
                                    batch=batch, group=g))
        d.append(pyglet.shapes.Circle(head[0], head[1], max(2.0, w * 0.8),
                                      color=(240, 200, 170), batch=batch,
                                      group=g))
        arm = math.sin(self.run.t * 3) * w * 2
        d.append(pyglet.shapes.Line(head[0], head[1] - w, head[0] + w * 2,
                                    head[1] + arm, thickness=max(1.5, w * 0.5),
                                    color=(60, 60, 90), batch=batch, group=g))

    def _ring(self, lens, x, z, r, y=0.0, n=28):
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            p = lens.see((x + r * math.cos(a), y, z + r * math.sin(a)))
            if p is None:
                return None
            pts.append((p[0], p[1]))
        return pts

    def _basket(self, lens, b, g) -> None:
        d, batch = self.drawn, self.batch
        run = self.run
        x, z = run.baskets[b]
        r = run.level.radius
        colour = BASKETS[b] if run.level.two else SINGLE
        floor = self._ring(lens, x, z, r)
        rim = self._ring(lens, x, z, r, y=model.RIM)
        if not floor or not rim:
            return
        d.append(pyglet.shapes.Polygon(*floor, color=polish.darker(colour, 0.5)
                                       + (150,), batch=batch, group=g))
        for (ax, ay), (bx, by) in zip(rim, rim[1:] + rim[:1]):
            d.append(pyglet.shapes.Line(ax, ay, bx, by, thickness=4,
                                        color=colour, batch=batch, group=g))
        for k in range(0, len(rim), 4):
            d.append(pyglet.shapes.Line(*floor[k], *rim[k], thickness=2,
                                        color=polish.lighter(colour, 0.3),
                                        batch=batch, group=g))
        aim = run.aim[b]
        if aim is not None:
            p = lens.see((aim[0], 0.0, aim[1]))
            if p:
                d.append(pyglet.shapes.Arc(p[0], p[1], 6, thickness=2,
                                           color=colour + (160,), batch=batch,
                                           group=g))

    def _ball(self, lens, k, g) -> None:
        d, batch = self.drawn, self.batch
        run = self.run
        ball = run.court.balls[k]
        x, y, z = model.where(ball, run.t, run.level.walls)
        if run.level.fog and z > model.FOG:
            return
        colour = BASKETS[ball.colour] if run.level.two else (250, 250, 245)
        if run.level.shadow:
            sh = self._ring(lens, x, z, 0.4, n=14)
            if sh:
                d.append(pyglet.shapes.Polygon(*sh, color=(20, 40, 20, 120),
                                               batch=batch, group=g))
        p = lens.see((x, y + 0.35, z))
        if not p:
            return
        r = max(2.0, lens.size(0.35, p[2]))
        d.append(pyglet.shapes.Circle(p[0], p[1], r,
                                      color=polish.darker(colour, 0.25),
                                      batch=batch, group=g))
        d.append(pyglet.shapes.Circle(p[0] - r * 0.15, p[1] + r * 0.15,
                                      r * 0.8, color=colour, batch=batch,
                                      group=g))
        d.append(pyglet.shapes.Circle(p[0] - r * 0.35, p[1] + r * 0.35,
                                      r * 0.25, color=(255, 255, 255, 200),
                                      batch=batch, group=g))

    def _landed(self, lens, k, g) -> None:
        d, batch = self.drawn, self.batch
        run = self.run
        ball = run.court.balls[k]
        x, z = model.where(ball, ball.t0 + ball.flight, run.level.walls)[0], \
            ball.land[1]
        ago = run.t - ball.t0 - ball.flight
        ring = self._ring(lens, x, z, 0.4 + ago * 2.0, n=20)
        if not ring:
            return
        ok = run.fate[k]
        colour = (110, 240, 140) if ok else (255, 80, 70)
        alpha = int(255 * max(0.0, 1.0 - ago / 0.7))
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            d.append(pyglet.shapes.Line(ax, ay, bx, by, thickness=3,
                                        color=colour + (alpha,), batch=batch,
                                        group=g))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   caught %d, dropped %d of %d allowed') % (
            self.rung, self.trial, self.total_trials, run.caught, run.missed,
            run.level.misses)
