# -*- coding: utf-8 -*-
"""Ferry on screen: a broad river, barges in their lanes, two banks.

Hold Up for ahead, Down for astern, Left and Right to turn (Up with a
turn does both). The lit pier, with its lamp and its waiting
passengers, is where to dock: come to rest inside its box and hold
there a moment. Streaks on the water run at the river's own speed,
fastest in midstream. From rung 16 a fog hides barges until they are
close.

For the agent boundary: ports 0 ahead, 1 astern, 2 turn left, 3 turn
right, 4 ahead and left, 5 ahead and right -- each for one step.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Optional, Tuple

import pyglet
from pyglet.window import key

from .. import ferry as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask

WATER_EDGE = (92, 170, 196)
WATER_MID = (34, 96, 150)
GRASS = (112, 172, 86)
SAND = (226, 206, 150)
PLANK = (150, 104, 62)
CARGO = ((222, 84, 66), (60, 130, 214), (240, 176, 50), (80, 170, 100))
HULL = (250, 250, 252)
STRIPE = (220, 64, 60)


class Ferry(ClockedTask):
    """Dock at every lit pier in turn."""

    instance: Optional['Ferry'] = None

    TITLE = 'Ferry'
    TASK_ID = 'ferry'
    PREFIX = 'FERRY'
    CATEGORY = 'planning'
    FEEDBACK = 3.0
    MODEL = model
    SUBSTEP = 1 / 60.0
    FOOTNOTE = _('Up: ahead   Down: astern   Left / Right: turn   '
                 'dock at the lit pier   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Carry the passengers across: dock at the lit pier')
        return ok

    def _held(self) -> Optional[int]:
        k = self.keys
        up = k[key.UP] or k[key.W]
        left = k[key.LEFT] or k[key.A]
        right = k[key.RIGHT] or k[key.D]
        if up and left:
            return model.AHEAD_LEFT
        if up and right:
            return model.AHEAD_RIGHT
        if up:
            return model.AHEAD
        if k[key.DOWN] or k[key.S]:
            return model.ASTERN
        if left:
            return model.LEFT
        if right:
            return model.RIGHT
        return None

    # --- geometry --------------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        s = min(width / model.WORLD_W, height / (model.WORLD_H + 2.5))
        x0 = left + (width - model.WORLD_W * s) / 2
        return x0, bottom, s

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    # --- the river, built once -----------------------------------------------------

    def _build_scenery(self) -> None:
        run = self.run
        river = run.river
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.WORLD_W * s, model.WORLD_H * s
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12, (60, 90, 60),
                    radius=14, shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        mid = (model.SOUTH + model.NORTH) / 2
        wx, wy = self._at(0, model.SOUTH)
        half = (mid - model.SOUTH) * s
        polish.gradient(out, batch, wx, wy, W, half, WATER_EDGE, WATER_MID,
                        bands=14, group=g0)
        polish.gradient(out, batch, wx, wy + half, W, half, WATER_MID,
                        WATER_EDGE, bands=14, group=g0)
        # Banks: sand then grass, with trees and cottages.
        draw = random.Random(river.gust_seed)
        for low, high, sand_at in ((0.0, model.SOUTH, model.SOUTH - 0.8),
                                   (model.NORTH, model.WORLD_H, model.NORTH)):
            gx, gy = self._at(0, low)
            out.append(pyglet.shapes.Rectangle(gx, gy, W, (high - low) * s,
                                               color=GRASS, batch=batch,
                                               group=g0))
            sx, sy = self._at(0, sand_at)
            out.append(pyglet.shapes.Rectangle(sx, sy, W, 0.8 * s,
                                               color=SAND, batch=batch,
                                               group=g1))
            for k in range(16):
                tx = draw.uniform(1, model.WORLD_W - 1)
                ty = draw.uniform(low + 0.4, high - 1.0) if high - low > 2 \
                    else low + 0.6
                px, py = self._at(tx, ty)
                if draw.random() < 0.7:
                    out.append(pyglet.shapes.Circle(
                        px, py, s * draw.uniform(0.5, 0.8),
                        color=polish.mix((50, 120, 60), (90, 160, 80),
                                         draw.random()),
                        batch=batch, group=g1))
                else:
                    out.append(pyglet.shapes.Rectangle(
                        px - 0.6 * s, py - 0.4 * s, 1.2 * s, 0.8 * s,
                        color=(244, 236, 220), batch=batch, group=g1))
                    out.append(pyglet.shapes.Triangle(
                        px - 0.8 * s, py + 0.4 * s, px + 0.8 * s,
                        py + 0.4 * s, px, py + 1.0 * s,
                        color=draw.choice(((200, 80, 60), (90, 110, 170))),
                        batch=batch, group=g1))
        # Piers: planked jetties out from the banks.
        for k, (px_w, py_w) in enumerate(river.piers):
            north = py_w > mid
            base = model.NORTH if north else model.SOUTH
            y_lo = min(base, py_w - 1.6 if north else py_w + 1.6)
            y_hi = max(base, py_w - 1.6 if north else py_w + 1.6)
            jx, jy = self._at(px_w + 2.6, y_lo)
            out.append(pyglet.shapes.Rectangle(jx, jy, 1.2 * s,
                                               (y_hi - y_lo) * s,
                                               color=PLANK, batch=batch,
                                               group=g1))
            for j in range(int(y_hi - y_lo) + 1):
                lx, ly = self._at(px_w + 2.6, y_lo + j)
                out.append(pyglet.shapes.Line(lx, ly, lx + 1.2 * s, ly,
                                              thickness=1,
                                              color=(110, 76, 44),
                                              batch=batch, group=g1))

    # --- each frame -------------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        river = run.river
        level = run.level
        self._scenery_fresh(self._frame())
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        t = run.t
        # Current streaks, each moving at its own depth's speed.
        for k in range(36):
            y = model.SOUTH + 1.0 + (k * 7.13) % (model.NORTH - model.SOUTH
                                                  - 2.0)
            c = model.current_at(level, y) + run.gust()
            x = (k * 11.7 + c * t) % (model.WORLD_W + 4) - 2
            ax, ay = self._at(x, y)
            d.append(pyglet.shapes.Line(ax, ay, ax - 0.6 * s * (0.5 + c), ay,
                                        thickness=2,
                                        color=(210, 236, 250, 90),
                                        batch=batch, group=card))
        # The target pier: its box, lamp and passengers.
        tx, ty = run.target()
        bx, by = self._at(tx - 2.2, ty - 1.6)
        docking = run.docked_since is not None
        hue = (120, 240, 150) if docking else (255, 214, 80)
        d.append(pyglet.shapes.Box(bx, by, 4.4 * s, 3.2 * s, thickness=3,
                                   color=hue, batch=batch, group=body))
        lx, ly = self._at(tx + 3.2, ty)
        polish.glow(d, batch, lx, ly, 2.2 * s, (255, 220, 120),
                    strength=110, group=card)
        d.append(pyglet.shapes.Circle(lx, ly, 0.35 * s, color=(255, 236, 160),
                                      batch=batch, group=text))
        for k in range(4):
            px, py = self._at(tx + 2.9 + (k % 2) * 0.6,
                              ty + (1.0 if ty > 20 else -1.0) * (0.8 + k * 0.5))
            d.append(pyglet.shapes.Circle(px, py, 0.28 * s,
                                          color=CARGO[k % len(CARGO)],
                                          batch=batch, group=text))
        if docking:
            share = min(1.0, (t - run.docked_since) / 2.0)
            d.append(pyglet.shapes.Arc(lx, ly, 0.9 * s, thickness=3,
                                       angle=360 * share, start_angle=90,
                                       color=(120, 240, 150), batch=batch,
                                       group=top))
        # Barges.
        for k, (bxw, byw, way) in enumerate(run.barge_positions()):
            if level.fog and math.hypot(bxw - run.x, byw - run.y) > model.FOG:
                continue
            hx, hy = model.BARGE_HALF
            px, py = self._at(bxw, byw)
            nose = way * hx * s
            d.append(pyglet.shapes.Polygon(
                (px - nose, py - hy * s), (px + nose * 0.75, py - hy * s),
                (px + nose, py), (px + nose * 0.75, py + hy * s),
                (px - nose, py + hy * s), color=(60, 56, 64), batch=batch,
                group=body))
            for j in range(3):
                cx = px - nose * 0.75 + way * j * 2.6 * s
                d.append(pyglet.shapes.Rectangle(
                    cx - 1.1 * s if way > 0 else cx - 1.1 * s, py - 0.9 * s,
                    2.2 * s, 1.8 * s, color=CARGO[(k + j) % len(CARGO)],
                    batch=batch, group=text))
            d.append(pyglet.shapes.Arc(px + nose, py, 1.4 * s, angle=120,
                                       start_angle=-60 if way > 0 else 120,
                                       thickness=2,
                                       color=(240, 250, 255, 170),
                                       batch=batch, group=text))
        # Fog: drifting banks of mist over the water.
        if level.fog:
            for k in range(7):
                fx = 11.0 + (k * 13.0 + t * 0.8) % (model.WORLD_W - 22.0)
                fy = model.SOUTH + 2 + (k * 5.3) % (model.NORTH - model.SOUTH
                                                    - 4)
                px, py = self._at(fx, fy)
                d.append(pyglet.shapes.Ellipse(px, py, 10.5 * s, 3.0 * s,
                                               color=(236, 240, 246, 120),
                                               batch=batch, group=top))
        # The wake and the ferry.
        for wx, wy, when in run.wake:
            age = t - when
            if age > 6:
                continue
            px, py = self._at(wx, wy)
            d.append(pyglet.shapes.Circle(
                px, py, (0.3 + age * 0.12) * s,
                color=(240, 250, 255, int(120 * (1 - age / 6))),
                batch=batch, group=card))
        fx, fy = self._at(run.x, run.y)
        h = math.radians(run.heading)
        ux, uy = math.cos(h), math.sin(h)
        px, py = -uy, ux
        L, B = 2.6 * s, 1.1 * s

        def pt(a, b):
            return (fx + ux * a + px * b, fy + uy * a + py * b)
        d.append(pyglet.shapes.Polygon(
            pt(L, 0), pt(L * 0.45, B), pt(-L, B * 0.9), pt(-L, -B * 0.9),
            pt(L * 0.45, -B), color=HULL, batch=batch, group=text))
        d.append(pyglet.shapes.Line(*pt(-L, 0), *pt(L * 0.8, 0),
                                    thickness=max(2.0, 0.25 * s),
                                    color=STRIPE, batch=batch, group=top))
        d.append(pyglet.shapes.Polygon(
            pt(-0.2 * L, 0.55 * B), pt(0.35 * L, 0.55 * B),
            pt(0.35 * L, -0.55 * B), pt(-0.2 * L, -0.55 * B),
            color=(70, 120, 180), batch=batch, group=top))
        if run.thrusting:
            for k in range(3):
                bxp, byp = pt(-L - (0.4 + 0.5 * k) * s * run.thrusting,
                              math.sin(t * 20 + k) * 0.3 * s)
                d.append(pyglet.shapes.Circle(bxp, byp, 0.25 * s,
                                              color=(255, 255, 255, 180),
                                              batch=batch, group=text))
        # Along the top: crossings and the time.
        top_y = y0 + (model.WORLD_H + 0.6) * s
        for k in range(1, len(river.piers)):
            done = k < run.leg
            now = k == run.leg
            cx = x0 + (0.6 + (k - 1) * 1.6) * s
            d.append(pyglet.shapes.Circle(
                cx + 0.6 * s, top_y + 0.6 * s, 0.55 * s,
                color=(80, 200, 130) if done else (255, 214, 80) if now
                else (190, 196, 208), batch=batch, group=body))
        share = max(0.0, 1.0 - t / level.seconds)
        bw = 20.0 * s
        bx = x0 + model.WORLD_W * s - bw - 0.5 * s
        polish.rounded(d, batch, bx, top_y + 0.2 * s, bw, 0.8 * s,
                       (190, 196, 208), radius=0.4 * s, group=card)
        if share > 0.02:
            polish.rounded(d, batch, bx, top_y + 0.2 * s, bw * share, 0.8 * s,
                           polish.mix((236, 80, 64), (60, 190, 120),
                                      min(1.0, share * 1.6)),
                           radius=0.4 * s, group=body)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   crossing %d of %d') % (
            self.rung, self.trial, self.total_trials, run.leg,
            len(run.river.piers) - 1)
