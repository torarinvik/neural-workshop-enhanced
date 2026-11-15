# -*- coding: utf-8 -*-
"""Crossroads on screen: a town seen from above, its lights and cars.

Click a junction (or press its number, 1-4) to switch its lights: the
green way goes amber, then all-red, then the other way goes green. Each
corner carries a signal head lit in its colour. Cars show brake lights
when they stop; ambulances flash red and blue and carry a ring that
empties as their patience runs out. Where a road enters town, stacked
markers count the cars waiting even to get on -- four of those is
gridlock.

For the agent boundary: ports 0-3 switch junctions 1-4 (only as many as
the town has).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Optional, Tuple

import pyglet
from pyglet.window import key

from .. import crossroads as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask

ASPHALT = (70, 74, 84)
KERB = (200, 200, 196)
BLOCK = (118, 168, 98)
ROOFS = ((204, 92, 72), (90, 120, 180), (220, 176, 90), (150, 110, 170),
         (120, 130, 140), (230, 140, 100))
CARS = ((236, 72, 80), (60, 150, 236), (250, 196, 50), (90, 200, 120),
        (180, 100, 230), (240, 130, 60), (240, 240, 244), (40, 44, 56))
LAMP = {'green': (60, 230, 120), 'amber': (255, 190, 40),
        'red': (240, 60, 56)}
ROAD = 3.8      # half width of a road


class Crossroads(ClockedTask):
    """No jams, no ambulance kept waiting."""

    instance: Optional['Crossroads'] = None

    TITLE = 'Crossroads'
    TASK_ID = 'crossroads'
    PREFIX = 'CROSSROADS'
    CATEGORY = 'decisions'
    FEEDBACK = 3.0
    MODEL = model
    SUBSTEP = 1 / 60.0
    FOOTNOTE = _('click a junction or press 1-4: switch its lights   '
                 'Esc: menu')
    EVENT_KEYS = {key._1: 0, key._2: 1, key._3: 2, key._4: 3}

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Switch the lights; keep the town moving')
        return ok

    def _click(self, x: float, y: float, button: int) -> None:
        if self.run is None:
            return
        s = self._frame()[2]
        for k, j in enumerate(self.run.town.junctions):
            px, py = self._at(j.x, j.y)
            if math.hypot(px - x, py - y) < ROAD * 2.2 * s:
                self.steer(k)
                return

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        s = min(width / model.WORLD_W, height / (model.WORLD_H + 2.0))
        x0 = left + (width - model.WORLD_W * s) / 2
        return x0, bottom, s

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    def _build_scenery(self) -> None:
        town = self.run.town
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.WORLD_W * s, model.WORLD_H * s
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12,
                    (50, 60, 50), radius=14, shade=pal.shadow,
                    group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        g2 = pyglet.graphics.Group(order=-12)
        out.append(pyglet.shapes.Rectangle(x0, y0, W, H, color=BLOCK,
                                           batch=batch, group=g0))
        xs = sorted({j.x for j in town.junctions})
        ys = sorted({j.y for j in town.junctions})
        # Buildings in the blocks between roads.
        draw = random.Random(len(town.arrivals))
        edges_x = [0.0] + xs + [model.WORLD_W]
        edges_y = [0.0] + ys + [model.WORLD_H]
        for a, b in zip(edges_x, edges_x[1:]):
            for c, d in zip(edges_y, edges_y[1:]):
                lo_x, hi_x = a + ROAD + 1.2, b - ROAD - 1.2
                lo_y, hi_y = c + ROAD + 1.2, d - ROAD - 1.2
                if a == 0.0:
                    lo_x = 1.0
                if b == model.WORLD_W:
                    hi_x = model.WORLD_W - 1.0
                if c == 0.0:
                    lo_y = 1.0
                if d == model.WORLD_H:
                    hi_y = model.WORLD_H - 1.0
                x = lo_x
                while x < hi_x - 3.0:
                    w = min(draw.uniform(4.0, 8.0), hi_x - x)
                    y = lo_y
                    while y < hi_y - 3.0:
                        h = min(draw.uniform(4.0, 8.0), hi_y - y)
                        if draw.random() < 0.8:
                            px, py = self._at(x, y)
                            roof = draw.choice(ROOFS)
                            out.append(pyglet.shapes.Rectangle(
                                px + 2, py - 2, (w - 0.8) * s,
                                (h - 0.8) * s, color=(40, 50, 40, 90),
                                batch=batch, group=g0))
                            out.append(pyglet.shapes.Rectangle(
                                px, py, (w - 0.8) * s, (h - 0.8) * s,
                                color=roof, batch=batch, group=g1))
                            out.append(pyglet.shapes.Rectangle(
                                px + (w - 0.8) * s * 0.6,
                                py + (h - 0.8) * s * 0.55, 1.2 * s, 1.0 * s,
                                color=polish.lighter(roof, 0.3),
                                batch=batch, group=g2))
                        else:
                            px, py = self._at(x + w / 2, y + h / 2)
                            out.append(pyglet.shapes.Circle(
                                px, py, min(w, h) * 0.35 * s,
                                color=(70, 140, 70), batch=batch, group=g1))
                        y += h
                    x += w
        # Roads with kerbs and centre dashes.
        for y in ys:
            px, py = self._at(0, y - ROAD)
            out.append(pyglet.shapes.Rectangle(px, py - 0.4 * s, W,
                                               (2 * ROAD + 0.8) * s,
                                               color=KERB, batch=batch,
                                               group=g1))
            out.append(pyglet.shapes.Rectangle(px, py, W, 2 * ROAD * s,
                                               color=ASPHALT, batch=batch,
                                               group=g2))
        for x in xs:
            px, py = self._at(x - ROAD, 0)
            out.append(pyglet.shapes.Rectangle(px - 0.4 * s, py,
                                               (2 * ROAD + 0.8) * s, H,
                                               color=KERB, batch=batch,
                                               group=g1))
            out.append(pyglet.shapes.Rectangle(px, py, 2 * ROAD * s, H,
                                               color=ASPHALT, batch=batch,
                                               group=g2))
        g3 = pyglet.graphics.Group(order=-11)
        for y in ys:
            for k in range(int(model.WORLD_W / 3)):
                xx = k * 3.0 + 0.5
                if any(abs(xx - x) < ROAD + 1.5 for x in xs):
                    continue
                px, py = self._at(xx, y)
                out.append(pyglet.shapes.Rectangle(px, py - 1, 1.5 * s, 2,
                                                   color=(240, 220, 120),
                                                   batch=batch, group=g3))
        for x in xs:
            for k in range(int(model.WORLD_H / 3)):
                yy = k * 3.0 + 0.5
                if any(abs(yy - y) < ROAD + 1.5 for y in ys):
                    continue
                px, py = self._at(x, yy)
                out.append(pyglet.shapes.Rectangle(px - 1, py, 2, 1.5 * s,
                                                   color=(240, 220, 120),
                                                   batch=batch, group=g3))
        # Zebra crossings at every junction.
        for j in town.junctions:
            for side in (-1, 1):
                for k in range(6):
                    off = -ROAD + 0.4 + k * (2 * ROAD - 0.8) / 5.5
                    px, py = self._at(j.x + side * (ROAD + 1.0), j.y + off)
                    out.append(pyglet.shapes.Rectangle(
                        px - 0.7 * s, py, 1.4 * s, 0.5 * s,
                        color=(236, 236, 236), batch=batch, group=g3))
                    px, py = self._at(j.x + off, j.y + side * (ROAD + 1.0))
                    out.append(pyglet.shapes.Rectangle(
                        px, py - 0.7 * s, 0.5 * s, 1.4 * s,
                        color=(236, 236, 236), batch=batch, group=g3))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        town = run.town
        self._scenery_fresh(self._frame())
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        t = run.t
        # Lights: a head at each corner, facing its own approach.
        for k, (j, light) in enumerate(zip(town.junctions, run.lights)):
            for axis, corners in (('EW', ((-1, -1), (1, 1))),
                                  ('NS', ((1, -1), (-1, 1)))):
                state = light.state(axis, t)
                hue = LAMP[state]
                for cx_s, cy_s in corners:
                    px, py = self._at(j.x + cx_s * (ROAD + 1.4),
                                      j.y + cy_s * (ROAD + 1.4))
                    polish.glow(d, batch, px, py, 1.6 * s, hue, strength=90,
                                group=card)
                    d.append(pyglet.shapes.Circle(px, py, 0.7 * s,
                                                  color=(30, 30, 36),
                                                  batch=batch, group=body))
                    d.append(pyglet.shapes.Circle(px, py, 0.5 * s,
                                                  color=hue, batch=batch,
                                                  group=text))
            jx, jy = self._at(j.x, j.y)
            if light.changing is not None:
                share = (t - light.changing) / (model.AMBER + model.ALL_RED)
                d.append(pyglet.shapes.Arc(jx, jy, ROAD * 0.8 * s,
                                           thickness=3,
                                           angle=360 * min(1.0, share),
                                           start_angle=90,
                                           color=(255, 200, 60), batch=batch,
                                           group=top))
            self._text(str(k + 1), jx, jy, max(9.0, 1.4 * s), bold=True,
                       colour=(255, 255, 255, 140))
        # Cars.
        for c in run.cars:
            path = town.paths[c.path]
            wx, wy = run.where(c)
            # A car still half off the map is not drawn: it would hang
            # over the board's edge, into the strip the verdict is read
            # from.
            if not (2.0 <= wx <= model.WORLD_W - 2.0 and
                    2.0 <= wy <= model.WORLD_H - 2.0):
                continue
            px, py = self._at(wx, wy)
            ux, uy = path.dx, path.dy
            L, B = 1.9 * s, 0.85 * s
            hue = (246, 246, 250) if c.ambulance else \
                CARS[c.colour % len(CARS)]

            def pt(a, b):
                return px + ux * a - uy * b, py + uy * a + ux * b
            corners = [pt(L, B), pt(-L, B), pt(-L, -B), pt(L, -B)]
            d.append(pyglet.shapes.Polygon(*corners, color=hue, batch=batch,
                                           group=body))
            d.append(pyglet.shapes.Polygon(
                pt(L * 0.45, B * 0.8), pt(-L * 0.3, B * 0.8),
                pt(-L * 0.3, -B * 0.8), pt(L * 0.45, -B * 0.8),
                color=polish.darker(hue, 0.3) if not c.ambulance
                else (200, 210, 230), batch=batch, group=text))
            stopped = c.v < 2.0
            for side in (-1, 1):
                bx, by = pt(-L, side * B * 0.6)
                d.append(pyglet.shapes.Circle(
                    bx, by, 0.28 * s,
                    color=(255, 40, 40) if stopped else (140, 30, 30),
                    batch=batch, group=top))
                hx, hy = pt(L, side * B * 0.6)
                d.append(pyglet.shapes.Circle(hx, hy, 0.25 * s,
                                              color=(255, 250, 210),
                                              batch=batch, group=top))
            if c.ambulance:
                blink = int(t * 6) % 2
                bx, by = pt(0.1 * L, 0)
                polish.glow(d, batch, bx, by, 2.2 * s,
                            (255, 60, 60) if blink else (60, 120, 255),
                            strength=140, group=card)
                d.append(pyglet.shapes.Rectangle(
                    bx - 0.3 * s, by - 0.3 * s, 0.6 * s, 0.6 * s,
                    color=(255, 60, 60) if blink else (60, 120, 255),
                    batch=batch, group=top))
                if c.waited > 0:
                    share = 1 - c.waited / model.AMBULANCE_WAIT
                    d.append(pyglet.shapes.Arc(
                        px, py, 2.6 * s, thickness=3,
                        angle=360 * max(0.0, share), start_angle=90,
                        color=(255, 80, 80), batch=batch, group=top))
        # Cars waiting to get into town, as stacked chevrons.
        for k, waiting in run.backlog.items():
            if not waiting:
                continue
            path = town.paths[k]
            for n, (amb, _born) in enumerate(waiting):
                ex = path.x0 + path.dx * (1.2 + 1.3 * n)
                ey = path.y0 + path.dy * (1.2 + 1.3 * n)
                if path.dx:
                    ey += -path.dx * 2.6
                else:
                    ex += path.dy * 2.6
                px, py = self._at(ex, ey)
                danger = (n + 1) / (model.BACKLOG + 1)
                d.append(pyglet.shapes.Circle(
                    px, py, 0.55 * s,
                    color=(255, 60, 60) if amb else polish.mix(
                        (255, 210, 60), (240, 50, 50), danger),
                    batch=batch, group=top))
        # The shift clock.
        top_y = y0 + (model.WORLD_H + 0.6) * s
        W = model.WORLD_W * s
        share = max(0.0, 1.0 - t / run.level.seconds)
        polish.rounded(d, batch, x0, top_y, W, 0.9 * s, (200, 200, 210),
                       radius=0.45 * s, group=card)
        if share > 0.02:
            polish.rounded(d, batch, x0, top_y, W * share, 0.9 * s,
                           (90, 150, 240), radius=0.45 * s, group=body)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   %d cars through   %d s left') % (
            self.rung, self.trial, self.total_trials, run.served,
            max(0, int(run.level.seconds - run.t)))
