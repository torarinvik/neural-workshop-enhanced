# -*- coding: utf-8 -*-
"""Dam Keeper on screen: a valley in steps, its reservoirs, the town.

Reservoirs step down the valley from left to right, each held by a
concrete dam with a gate. Q, W and E open the gates of dams 1, 2 and 3
a notch; A, S and D shut them a notch (or click a gate's upper or
lower half). Lamps on each gate show its notch, and the jet out of it
shows the flow. Water let out runs down the river to the next
reservoir as drifting foam. Storm clouds roll in from the left with
rain beneath them; from rung 16 they show only once over the valley.
Past the last dam the town's river carries a red flood line.

For the agent boundary: ports 0, 2 and 4 open dams 1-3 a notch; 1, 3
and 5 shut them a notch.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import pyglet
from pyglet.window import key

from .. import damkeeper as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask

LEFT_W, RIGHT_W = -30.0, 124.0     # world x shown: forecast to town
WORLD_H = 60.0
STEP = 11.0                        # each reservoir sits this much lower
DEPTH = 16.0                       # a full reservoir's depth
WATER_TOP = (96, 170, 222)
WATER_DEEP = (30, 82, 150)
ROCK = (122, 108, 96)
HILL = (104, 150, 92)
CONCRETE = (200, 198, 192)


class DamKeeper(ClockedTask):
    """Through every storm: no dam over, no town flooded, no reservoir
    dry."""

    instance: Optional['DamKeeper'] = None

    TITLE = 'Dam Keeper'
    TASK_ID = 'dam_keeper'
    PREFIX = 'DAMKEEPER'
    CATEGORY = 'decisions'
    FEEDBACK = 3.0
    MODEL = model
    SUBSTEP = 1 / 30.0
    FOOTNOTE = _('Q W E: open gates 1-3 a notch   A S D: shut a notch   '
                 '(or click a gate)   Esc: menu')
    EVENT_KEYS = {key.Q: 0, key.A: 1, key.W: 2, key.S: 3, key.E: 4,
                  key.D: 5}

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Make room before the rain; never flood the town')
        return ok

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        span = RIGHT_W - LEFT_W
        s = min(width / span, height / (WORLD_H + 3.0))
        x0 = left + (width - span * s) / 2 - LEFT_W * s
        return x0, bottom, s

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    def _floor(self, k: int) -> float:
        """The bed of reservoir *k*."""
        return 34.0 - k * STEP - (3 - self.run.level.dams) * 0.0

    def _dam_x(self, k: int) -> float:
        return self.run.valley.spans[k][1] - 2.0

    def _click(self, x: float, y: float, button: int) -> None:
        if self.run is None:
            return
        s = self._frame()[2]
        for k in range(self.run.level.dams):
            gx, gy = self._at(self._dam_x(k), self._floor(k) + DEPTH * 0.5)
            if abs(x - gx) < 3.0 * s and abs(y - gy) < DEPTH * 0.6 * s:
                self.steer(2 * k + (0 if y > gy else 1))
                return

    # --- the valley, built once --------------------------------------------------

    def _build_scenery(self) -> None:
        run = self.run
        valley = run.valley
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        lx, _ly = self._at(LEFT_W, 0)
        W = (RIGHT_W - LEFT_W) * s
        H = WORLD_H * s
        polish.card(out, batch, lx - 6, y0 - 6, W + 12, H + 12, (60, 70, 90),
                    radius=14, shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        polish.gradient(out, batch, lx, y0, W, H, (196, 214, 232),
                        (96, 140, 196), bands=20, group=g0)
        # The forecast strip, left of the valley.
        fx, fy = self._at(LEFT_W, WORLD_H - 16)
        out.append(pyglet.shapes.Rectangle(fx, fy, (0 - LEFT_W) * s, 16 * s,
                                           color=(80, 90, 120, 60),
                                           batch=batch, group=g0))
        # Far mountains behind everything.
        ridge = [(0.0, 30.0), (12.0, 46.0), (26.0, 38.0), (40.0, 50.0),
                 (55.0, 36.0), (70.0, 44.0), (86.0, 30.0), (100.0, 34.0),
                 (112.0, 24.0), (RIGHT_W, 20.0)]
        for (ax, ay), (bx, by) in zip(ridge, ridge[1:]):
            pa, pb = self._at(ax, ay), self._at(bx, by)
            base_a, base_b = self._at(ax, 0), self._at(bx, 0)
            out.append(pyglet.shapes.Polygon(
                base_a, pa, pb, base_b, color=(150, 160, 196), batch=batch,
                group=g0))
        # Hillsides stepping down, one ledge a reservoir.
        n = run.level.dams
        for k in range(n):
            lo, hi = valley.spans[k]
            bed = self._floor(k)
            px, py = self._at(lo, 0)
            out.append(pyglet.shapes.Rectangle(px, py, (hi - lo) * s,
                                               bed * s, color=ROCK,
                                               batch=batch, group=g1))
        # The town's plain beyond the last dam.
        tx, ty = self._at(model.VALLEY, 0)
        out.append(pyglet.shapes.Rectangle(tx, ty, (RIGHT_W - model.VALLEY)
                                           * s, 6.0 * s, color=(150, 186, 110),
                                           batch=batch, group=g1))
        houses = ((104.0, (210, 90, 70)), (110.0, (90, 120, 190)),
                  (116.0, (230, 180, 90)), (120.0, (150, 100, 170)))
        for hx_w, roof in houses:
            px, py = self._at(hx_w, 6.0)
            out.append(pyglet.shapes.Rectangle(px - 1.8 * s, py, 3.6 * s,
                                               3.0 * s,
                                               color=(244, 236, 220),
                                               batch=batch, group=g1))
            out.append(pyglet.shapes.Triangle(
                px - 2.2 * s, py + 3.0 * s, px + 2.2 * s, py + 3.0 * s, px,
                py + 5.0 * s, color=roof, batch=batch, group=g1))
        # Dams: concrete wedges with their gates.
        for k in range(n):
            bed = self._floor(k)
            dx = self._dam_x(k)
            px, py = self._at(dx, bed)
            out.append(pyglet.shapes.Polygon(
                (px - 1.5 * s, py), (px + 3.5 * s, py - 4 * s),
                (px + 3.5 * s, py + (DEPTH + 2) * s),
                (px - 0.5 * s, py + (DEPTH + 2) * s),
                color=CONCRETE, batch=batch, group=g1))

    # --- each frame ------------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        valley = run.valley
        level = run.level
        self._scenery_fresh(self._frame())
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        t = run.t
        n = level.dams
        # Clouds and rain.
        for st in valley.storms:
            back, front = run.storm_span(st)
            if front < LEFT_W or back > model.VALLEY + 10:
                continue
            lo, hi = max(back, LEFT_W + 4.0), min(front, RIGHT_W - 4.0)
            if level.hidden:
                lo = max(lo, 0.0)
                if hi <= lo:
                    continue
            cy = WORLD_H - 6
            for k in range(int((hi - lo) / 4) + 1):
                cx = lo + k * 4 + 2
                if cx > hi:
                    break
                px, py = self._at(cx, cy + math.sin(k * 1.3) * 1.2)
                d.append(pyglet.shapes.Circle(px, py, 3.4 * s,
                                              color=(90, 96, 116),
                                              batch=batch, group=body))
                d.append(pyglet.shapes.Circle(px - 1 * s, py + 1.2 * s,
                                              2.4 * s,
                                              color=(120, 126, 146),
                                              batch=batch, group=text))
                if cx >= 0:
                    for j in range(3):
                        ry = (cy - 3 - ((t * 30 + j * 9 + k * 5) % 22))
                        rx, rpy = self._at(cx - 1 + j, ry)
                        d.append(pyglet.shapes.Line(
                            rx, rpy, rx - 0.4 * s, rpy - 2.2 * s,
                            thickness=1, color=(200, 220, 255, 170),
                            batch=batch, group=card))
        # Reservoirs.
        for k in range(n):
            lo, hi = valley.spans[k]
            bed = self._floor(k)
            share = min(1.0, run.water[k] / 100.0)
            depth = DEPTH * share
            px, py = self._at(lo + 1.0, bed)
            w = (self._dam_x(k) - lo - 0.5) * s
            polish.gradient(d, batch, px, py, w, max(1.0, depth * s),
                            WATER_DEEP, WATER_TOP, bands=6, group=card)
            for j in range(int(w / (3 * s))):
                wx = px + j * 3 * s + (t * 8 % 3) * s
                if wx < px + w - 2 * s:
                    d.append(pyglet.shapes.Arc(
                        wx, py + depth * s, 0.8 * s, angle=180,
                        start_angle=0, thickness=1,
                        color=(220, 240, 255), batch=batch, group=body))
            # Full and low marks on the dam face.
            mx, _my = self._at(self._dam_x(k) - 0.6, 0)
            for frac, hue in ((1.0, (240, 70, 60)),
                              (model.LOW / 100.0, (250, 190, 60))):
                _mx, my = self._at(0, bed + DEPTH * frac)
                d.append(pyglet.shapes.Line(mx - 2.5 * s, my, mx, my,
                                            thickness=2, color=hue,
                                            batch=batch, group=text))
            danger = run.water[k] > 85 or run.water[k] < model.LOW + 5
            lx, ly = self._at((lo + hi) / 2, bed + DEPTH + 2.2)
            self._text('%d%%' % int(run.water[k]), lx, ly,
                       max(9.0, 1.6 * s), bold=True,
                       colour=(220, 60, 50, 255) if danger
                       else (30, 40, 70, 255))
            # The gate: notch lamps and its jet.
            gx, gy = self._at(self._dam_x(k) + 1.0, bed + 2.0)
            for j in range(model.NOTCHES):
                on = j < run.gate[k]
                d.append(pyglet.shapes.Circle(
                    gx, gy + (3.0 + j * 2.4) * s, 0.8 * s,
                    color=(90, 220, 255) if on else (90, 96, 110),
                    batch=batch, group=top))
            flow = run.outflow(k)
            if flow > 0:
                share = flow / model.FLOW
                jx, jy = self._at(self._dam_x(k) + 3.5, bed + 1.0)
                d.append(pyglet.shapes.Polygon(
                    (jx, jy + 0.6 * s), (jx, jy - (0.4 + share) * s),
                    (jx + (4 + 4 * share) * s, jy - 4 * s),
                    (jx + (4 + 4 * share) * s, jy - (3 - share * 2) * s),
                    color=(210, 236, 255), batch=batch, group=text))
                for j in range(4):
                    ph = (t * 1.5 + j * 0.25) % 1.0
                    d.append(pyglet.shapes.Circle(
                        jx + (2 + 6 * ph) * s, jy - 3.5 * s * ph,
                        (0.4 + 0.5 * share) * s,
                        color=(255, 255, 255, int(200 * (1 - ph))),
                        batch=batch, group=top))
            self._text(str(k + 1), gx, gy + 13.6 * s, max(8.0, 1.3 * s),
                       bold=True, colour=(40, 40, 60, 255))
        # Water on its way between dams: foam along the river.
        for k in range(1, n):
            amount = run.in_pipe(k)
            if amount <= 0.05:
                continue
            ax = self._dam_x(k - 1) + 6
            bx = valley.spans[k][0] + 2
            ay = self._floor(k - 1) - 3.5
            by = self._floor(k) + 1.0
            for j in range(int(min(10, 2 + amount))):
                ph = (t * 0.25 + j / 10.0) % 1.0
                px, py = self._at(ax + (bx - ax) * ph, ay + (by - ay) * ph)
                d.append(pyglet.shapes.Circle(px, py, 0.6 * s,
                                              color=(160, 210, 245),
                                              batch=batch, group=body))
        # The town's river and its flood line.
        rx, ry = self._at(self._dam_x(n - 1) + 4, 1.0)
        rw = (RIGHT_W - self._dam_x(n - 1) - 5) * s
        depth = 4.0 * min(1.4, run.town / level.flood)
        flooding = run.town > level.flood
        d.append(pyglet.shapes.Rectangle(
            rx, ry, rw, max(1.0, depth * s),
            color=(220, 80, 70) if flooding else WATER_TOP, batch=batch,
            group=card))
        fx, fy = self._at(0, 1.0 + 4.0)
        d.append(pyglet.shapes.Line(rx, fy, rx + rw, fy, thickness=2,
                                    color=(240, 60, 50), batch=batch,
                                    group=top))
        if flooding:
            polish.glow(d, batch, rx + rw / 2, fy, 8 * s, (255, 80, 60),
                        strength=90, group=card)
        # The clock.
        lx, _ly = self._at(LEFT_W, 0)
        W = (RIGHT_W - LEFT_W) * s
        top_y = y0 + (WORLD_H + 0.8) * s
        share = max(0.0, 1.0 - t / model.SECONDS)
        polish.rounded(d, batch, lx, top_y, W, 1.4 * s, (200, 204, 214),
                       radius=0.7 * s, group=card)
        if share > 0.02:
            polish.rounded(d, batch, lx, top_y, W * share, 1.4 * s,
                           (90, 150, 240), radius=0.7 * s, group=body)
        self._text(_('forecast') if not level.hidden else _('no forecast'),
                   self._at(LEFT_W / 2, WORLD_H - 17.5)[0],
                   self._at(0, WORLD_H - 17.5)[1], max(8.0, 1.3 * s),
                   colour=(40, 50, 80, 200))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   %d s left') % (
            self.rung, self.trial, self.total_trials,
            max(0, int(model.SECONDS - run.t)))
