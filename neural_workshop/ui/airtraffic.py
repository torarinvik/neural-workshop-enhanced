# -*- coding: utf-8 -*-
"""Air Traffic on screen: a radar scope, runways, storms and planes.

Click a plane (or press its number, 1-8) to pick it, then: H hold,
A or Left turn left, D or Right turn right, L (or a click on its
runway) clear it to land. Each plane is painted its runway's colour
and trails its last positions; a picked plane wears a white ring, two
planes getting close a red one. Holding planes show their circle.
The sweep goes round as a radar's would.

For the agent boundary: ports 0-7 pick the plane in that slot; 8 hold,
9 turn left, 10 turn right, 11 land.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from collections import deque
from typing import Deque, Dict, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import airtraffic as model
from ..i18n import _
from . import polish
from .rungtask import RungTask

SCOPE = (10, 22, 34)
SCOPE_EDGE = (20, 40, 58)
RING = (34, 70, 84)
SWEEP = (60, 220, 160)
RUNWAY_COLOURS = ((255, 160, 50), (70, 210, 240))
SINGLE = (240, 240, 250)
STORM = (150, 90, 220)
DANGER = (255, 70, 70)
LABEL = (226, 236, 244, 255)


class AirTraffic(RungTask):
    """Land every plane without losing one."""

    instance: Optional['AirTraffic'] = None

    TITLE = 'Air Traffic'
    TASK_ID = 'air_traffic'
    PREFIX = 'AIRTRAFFIC'
    CATEGORY = 'planning'
    FEEDBACK = 3.0
    FOOTNOTE = _('click or 1-8: pick a plane   H hold   A/D turn   '
                 'L or click its runway: land   Esc: menu')

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        self.last_tick = 0.0
        self.trails: Dict[int, Deque[Tuple[float, float]]] = {}
        self.trail_clock = 0.0
        super().__init__()

    def _clear_trial(self) -> None:
        self.run = None
        self.trails = {}

    def _deal(self) -> bool:
        self.run = model.Run(model.deal(self.rung, rng=self.rng))
        self.last_tick = self.clock()
        self.trails = {}
        self.trail_clock = 0.0
        self.message = _('Land every plane on the runway of its colour')
        return True

    # --- controls --------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase == self.PLAY and self.run is not None:
            model.apply(self.run, port)

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._8:
            self.steer(symbol - key._1)
        elif symbol == key.H:
            self.steer(model.SLOTS + model.HOLD)
        elif symbol in (key.A, key.LEFT):
            self.steer(model.SLOTS + model.LEFT)
        elif symbol in (key.D, key.RIGHT):
            self.steer(model.SLOTS + model.RIGHT)
        elif symbol == key.L:
            self.steer(model.SLOTS + model.LAND)

    def _click(self, x: float, y: float, button: int) -> None:
        run = self.run
        if run is None:
            return
        s = self._frame()[2]
        best, slot = (5.0 * s) ** 2, None
        for p in run.planes:
            px, py = self._at(p.x, p.y)
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best:
                best, slot = d, p.slot
        if slot is not None:
            self.steer(slot)
            return
        if run.selected is not None:
            picked = run.plane_in(run.selected)
            for k, rw in enumerate(run.sky.runways):
                rx, ry = self._at(rw.x, rw.y)
                if (rx - x) ** 2 + (ry - y) ** 2 < (rw.length * 0.7 * s) ** 2 \
                        and picked is not None and picked.runway == k:
                    self.steer(model.SLOTS + model.LAND)
                    return

    def _tick(self) -> None:
        now = self.clock()
        dt = max(0.0, min(0.1, now - self.last_tick))
        self.last_tick = now
        run = self.run
        steps = max(1, int(math.ceil(dt / (1 / 60.0))))
        for _s in range(steps):
            run.step(dt / steps)
            if run.result is not None:
                break
        self.trail_clock += dt
        if self.trail_clock >= 0.5:
            self.trail_clock = 0.0
            for p in run.planes:
                trail = self.trails.setdefault(p.number, deque(maxlen=10))
                trail.append((p.x, p.y))
        if run.result is not None:
            self._judge(*run.result)
        else:
            self._redraw()

    # --- geometry --------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        scale = min(width / model.WORLD_W, height / model.WORLD_H)
        x0 = left + (width - model.WORLD_W * scale) / 2
        return x0, bottom, scale

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    def _colour(self, runway: int) -> Tuple[int, int, int]:
        if len(self.run.sky.runways) == 1:
            return SINGLE
        return RUNWAY_COLOURS[runway % 2]

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        sky = run.sky
        x0, y0, s = self._frame()
        W, H = model.WORLD_W * s, model.WORLD_H * s
        batch = self.batch
        d = self.drawn
        pal = polish.palette(self.dark)
        polish.card(d, batch, x0 - 5, y0 - 5, W + 10, H + 10, SCOPE_EDGE,
                    radius=16, shade=pal.shadow, group=polish.STAGE)
        polish.rounded(d, batch, x0, y0, W, H, SCOPE, radius=12,
                       group=polish.CARD)
        cx, cy = self._at(model.WORLD_W / 2, model.WORLD_H / 2)
        # Range rings and a grid.
        grid = pyglet.graphics.Group(order=-14)
        for k in range(1, 5):
            d.append(pyglet.shapes.Arc(
                cx, cy, k * 0.12 * H, thickness=1, color=RING, batch=batch,
                group=grid))
        for gx in range(10, int(model.WORLD_W), 10):
            ax, ay = self._at(gx, 1)
            bx, by = self._at(gx, model.WORLD_H - 1)
            d.append(pyglet.shapes.Line(ax, ay, bx, by, thickness=1,
                                        color=(16, 32, 46), batch=batch,
                                        group=grid))
        for gy in range(10, int(model.WORLD_H), 10):
            ax, ay = self._at(1, gy)
            bx, by = self._at(model.WORLD_W - 1, gy)
            d.append(pyglet.shapes.Line(ax, ay, bx, by, thickness=1,
                                        color=(16, 32, 46), batch=batch,
                                        group=grid))
        # The sweep: a fan of fading slices behind a bright edge.
        sweep_g = pyglet.graphics.Group(order=-13)
        angle = (run.t * 90.0) % 360.0
        reach = min(W, H) * 0.49
        for k in range(8):
            d.append(pyglet.shapes.Sector(
                cx, cy, reach, angle=6.0, start_angle=angle - 6.0 * (k + 1),
                color=SWEEP + (max(4, 46 - k * 6),), batch=batch,
                group=sweep_g))
        rad = math.radians(angle)
        d.append(pyglet.shapes.Line(
            cx, cy, cx + math.cos(rad) * reach, cy + math.sin(rad) * reach,
            thickness=2, color=SWEEP + (150,), batch=batch, group=sweep_g))
        # Storms.
        for st in run.storms:
            px, py = self._at(st.x, st.y)
            r = st.radius * s
            for k, a in enumerate((40, 60, 90, 120)):
                d.append(pyglet.shapes.Circle(
                    px + math.sin(run.t * 0.7 + k) * r * 0.06,
                    py + math.cos(run.t * 0.5 + k) * r * 0.06,
                    r * (1.15 - k * 0.18), color=polish.mix(
                        STORM, (60, 30, 120), k * 0.2) + (a,),
                    batch=batch, group=self.card_group))
            if int(run.t * 3 + st.radius) % 7 == 0:
                bolt = [(0.0, 0.5), (-0.2, 0.0), (0.05, 0.05), (-0.15, -0.5),
                        (0.25, 0.1), (0.0, 0.05), (0.2, 0.5)]
                pts = [(px + bx * r, py + by * r) for bx, by in bolt]
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    d.append(pyglet.shapes.Line(
                        ax, ay, bx, by, thickness=2, color=(255, 250, 180),
                        batch=batch, group=self.text_group))
        # Runways.
        for k, rw in enumerate(sky.runways):
            self._runway(k, rw, s)
        # Planes: trails, hold circles, bodies, labels.
        warn = run.close_pairs()
        hot = {p.number for pair in warn for p in pair}
        hold_r = sky.level.speed / math.radians(model.HOLD_RATE)
        for p in run.planes:
            colour = self._colour(p.runway)
            trail = self.trails.get(p.number, ())
            for i, (tx, ty) in enumerate(trail):
                px, py = self._at(tx, ty)
                d.append(pyglet.shapes.Circle(
                    px, py, max(1.2, 0.35 * s),
                    color=colour + (40 + 18 * i,), batch=batch,
                    group=self.card_group))
            if p.mode == 'hold':
                h = math.radians(p.heading + 90)
                hx, hy = self._at(p.x + math.cos(h) * hold_r,
                                  p.y + math.sin(h) * hold_r)
                d.append(pyglet.shapes.Arc(
                    hx, hy, hold_r * s, thickness=1,
                    color=colour + (90,), batch=batch,
                    group=self.card_group))
            if p.cleared:
                fx, fy = self._at(*run.fix(p.runway))
                px, py = self._at(p.x, p.y)
                self._dashes(px, py, fx, fy, colour + (120,))
            self._plane(p, colour, s, p.number in hot,
                        run.selected == p.slot)
        if run.lost_at is not None:
            lx, ly = self._at(*run.lost_at)
            d.append(pyglet.shapes.Star(lx, ly, 5 * s, 2 * s, 10,
                                        color=(255, 180, 60), batch=batch,
                                        group=self.top_group))
        # Notes: go-arounds and landings, fading.
        for when, words, nx, ny in run.notes[-6:]:
            age = run.t - when
            if age < 3.0:
                px, py = self._at(nx, ny + 6 + age * 2)
                self._text(words, px, py, max(7.0, 1.7 * s), bold=True,
                           colour=(255, 230, 140, int(255 * (1 - age / 3))),
                           group=self.top_group)
        # Arrivals still to come, and planes down, along the top edge.
        tx, ty = self._at(3, model.WORLD_H - 4)
        self._text(_('down %d of %d   inbound %d') % (
            len(run.landed), len(sky.arrivals), len(run.waiting)), tx, ty,
            max(8.0, 2.0 * s), anchor='left', colour=LABEL,
            group=self.top_group)
        if sky.shift is not None and not run.flipped:
            wx, wy = self._at(model.WORLD_W - 4, model.WORLD_H - 4)
            self._text(_('wind turns in %d s') % max(0, sky.shift - run.t),
                       wx, wy, max(8.0, 2.0 * s), anchor='right',
                       colour=(255, 220, 120, 255), group=self.top_group)

    def _dashes(self, ax, ay, bx, by, colour) -> None:
        length = math.hypot(bx - ax, by - ay)
        n = int(length // 10)
        for k in range(0, n, 2):
            f0, f1 = k / max(n, 1), (k + 1) / max(n, 1)
            self.drawn.append(pyglet.shapes.Line(
                ax + (bx - ax) * f0, ay + (by - ay) * f0,
                ax + (bx - ax) * f1, ay + (by - ay) * f1, thickness=1.5,
                color=colour, batch=self.batch, group=self.card_group))

    def _runway(self, k: int, rw: model.Runway, s: float) -> None:
        run = self.run
        d, batch = self.drawn, self.batch
        h = math.radians(run.runway_heading(k))
        ux, uy = math.cos(h), math.sin(h)
        nx, ny = -uy, ux
        half_l, half_w = rw.length / 2, 1.6
        colour = self._colour(k)

        def at(a, b):
            return self._at(rw.x + ux * a + nx * b, rw.y + uy * a + ny * b)
        body = [at(-half_l, -half_w), at(half_l, -half_w),
                at(half_l, half_w), at(-half_l, half_w)]
        edge = [at(-half_l - 0.6, -half_w - 0.6), at(half_l + 0.6, -half_w - 0.6),
                at(half_l + 0.6, half_w + 0.6), at(-half_l - 0.6, half_w + 0.6)]
        d.append(pyglet.shapes.Polygon(*edge, color=colour, batch=batch,
                                       group=self.card_group))
        d.append(pyglet.shapes.Polygon(*body, color=(54, 58, 66),
                                       batch=batch, group=self.body_group))
        for a in range(-int(half_l) + 3, int(half_l) - 1, 3):
            p0, p1 = at(a, 0), at(a + 1.4, 0)
            d.append(pyglet.shapes.Line(p0[0], p0[1], p1[0], p1[1],
                                        thickness=max(1.0, 0.3 * s),
                                        color=(240, 240, 240), batch=batch,
                                        group=self.text_group))
        for b in (-1.0, -0.4, 0.4, 1.0):
            p0, p1 = at(-half_l + 0.4, b), at(-half_l + 2.0, b)
            d.append(pyglet.shapes.Line(p0[0], p0[1], p1[0], p1[1],
                                        thickness=max(1.0, 0.35 * s),
                                        color=(240, 240, 240), batch=batch,
                                        group=self.text_group))
        # The way in: an arrow off the threshold, and the approach fix.
        tip = at(-half_l - 1.0, 0)
        tail = at(-half_l - 7.0, 0)
        d.append(pyglet.shapes.Line(tail[0], tail[1], tip[0], tip[1],
                                    thickness=2, color=colour, batch=batch,
                                    group=self.text_group))
        a1, a2 = at(-half_l - 2.6, 1.2), at(-half_l - 2.6, -1.2)
        d.append(pyglet.shapes.Triangle(tip[0], tip[1], a1[0], a1[1],
                                        a2[0], a2[1], color=colour,
                                        batch=batch, group=self.text_group))
        fx, fy = self._at(*run.fix(k))
        d.append(pyglet.shapes.Star(fx, fy, 1.4 * s, 0.6 * s, 4,
                                    color=colour + (180,), batch=batch,
                                    group=self.card_group))
        if run.closed(k):
            c0, c1, c2, c3 = body
            for (ax, ay), (bx, by) in ((c0, c2), (c1, c3)):
                d.append(pyglet.shapes.Line(ax, ay, bx, by, thickness=4,
                                            color=DANGER, batch=batch,
                                            group=self.top_group))
        elif run.t < run.busy_until[k]:
            mx, my = self._at(rw.x, rw.y)
            d.append(pyglet.shapes.Circle(mx, my, 1.2 * s,
                                          color=(255, 220, 80), batch=batch,
                                          group=self.top_group))

    def _plane(self, p: model.Plane, colour, s: float, hot: bool,
               picked: bool) -> None:
        d, batch = self.drawn, self.batch
        h = math.radians(p.heading)
        ca, sa = math.cos(h), math.sin(h)
        size = 1.15

        def at(a, b):
            return self._at(p.x + (a * ca - b * sa) * size,
                            p.y + (a * sa + b * ca) * size)
        px, py = self._at(p.x, p.y)
        if picked:
            d.append(pyglet.shapes.Arc(px, py, 4.2 * s, thickness=2,
                                       color=(255, 255, 255), batch=batch,
                                       group=self.top_group))
        if hot:
            d.append(pyglet.shapes.Arc(px, py, model.SEPARATION * s,
                                       thickness=2, color=DANGER,
                                       batch=batch, group=self.top_group))
        dark = polish.darker(colour, 0.45)
        shapes = (
            [at(2.2, 0), at(1.4, 0.45), at(-1.8, 0.45), at(-2.0, 0),
             at(-1.8, -0.45), at(1.4, -0.45)],                 # fuselage
            [at(0.6, 0.3), at(-0.6, 2.4), at(-1.1, 2.4), at(-0.4, 0.3)],
            [at(0.6, -0.3), at(-0.6, -2.4), at(-1.1, -2.4), at(-0.4, -0.3)],
            [at(-1.4, 0.3), at(-2.0, 1.1), at(-2.3, 1.1), at(-1.9, 0.2)],
            [at(-1.4, -0.3), at(-2.0, -1.1), at(-2.3, -1.1), at(-1.9, -0.2)],
        )
        shade = [(x + 0.35 * s, y - 0.5 * s) for x, y in shapes[0]]
        d.append(pyglet.shapes.Polygon(*shade, color=(0, 0, 0, 90),
                                       batch=batch, group=self.body_group))
        for k, poly in enumerate(shapes):
            d.append(pyglet.shapes.Polygon(
                *poly, color=colour if k == 0 else polish.mix(colour, dark,
                                                              0.35),
                batch=batch, group=self.text_group))
        # The label: slot, what it is doing, and its fuel.
        mode = {'hold': 'H', 'free': '>', 'approach': 'L',
                'final': 'L'}.get(p.mode, '')
        lx, ly = px + 3.2 * s, py + 2.6 * s
        polish.rounded(d, batch, lx - 0.4 * s, ly - 1.3 * s, 6.4 * s,
                       2.6 * s, (14, 26, 38, 210), radius=0.6 * s,
                       group=self.text_group)
        self._text('%d %s' % (p.slot + 1, mode), lx + 2.8 * s, ly,
                   max(7.0, 1.6 * s), bold=True,
                   colour=colour + (255,), group=self.top_group)
        if p.fuel is not None and p.arrival.fuel:
            share = max(0.0, p.fuel / p.arrival.fuel)
            bar = 6.0 * s
            fuel_colour = (90, 220, 120) if share > 0.4 else \
                (250, 200, 60) if share > 0.2 else DANGER
            polish.rounded(d, batch, lx - 0.4 * s, ly - 2.3 * s,
                           bar * share, 0.6 * s, fuel_colour,
                           radius=0.3 * s, group=self.top_group)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        picked = run.plane_in(run.selected) if run.selected is not None \
            else None
        words = _('rung %d  %d/%d   %d s left') % (
            self.rung, self.trial, self.total_trials,
            max(0, int(run.sky.seconds - run.t)))
        if picked is not None:
            words += _('   plane %d picked') % (picked.slot + 1)
        return words
