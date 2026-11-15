# -*- coding: utf-8 -*-
"""Sokoban Live on screen: a lit warehouse with guards on patrol.

Arrows step the worker (yellow hard hat) and push crates. Pads glow
teal; a crate on a pad turns gold. Guards are red robots whose torch
beam shows which way they walk, with a ring that fills toward their
next step. Shutters are striped doors with a ring counting to their
next change. Along the top, the pads covered and the time left.

For the agent boundary: ports 0-3 step up, down, left and right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import sokobanlive as model
from ..i18n import _
from . import polish
from .rungtask import RungTask

CONCRETE = (190, 196, 204)
SEAM = (170, 176, 186)
RACK = (52, 64, 92)
RACK_EDGE = (36, 44, 66)
CRATE = (196, 132, 66)
CRATE_DARK = (148, 94, 44)
CRATE_HOME = (240, 192, 60)
PAD = (40, 200, 190)
GUARD = (220, 64, 72)
HAT = (255, 206, 40)
VEST = (255, 128, 40)
SHUTTER = (230, 180, 40)
INK = (244, 246, 250, 255)


class SokobanLive(RungTask):
    """Cover every pad before the time runs out, and dodge the guards."""

    instance: Optional['SokobanLive'] = None

    TITLE = 'Sokoban Live'
    TASK_ID = 'sokoban_live'
    PREFIX = 'SOKOBANLIVE'
    CATEGORY = 'planning'
    FEEDBACK = 3.0
    FOOTNOTE = _('arrows: step and push   Esc: menu')

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        self.last_tick = 0.0
        self.scenery: List[object] = []
        self.scenery_key = None
        super().__init__()

    def _drop(self) -> None:
        for item in self.scenery:
            try:
                item.delete()
            except Exception:
                pass
        self.scenery = []
        self.scenery_key = None

    def _clear_trial(self) -> None:
        self.run = None
        self._drop()

    def close(self) -> None:
        if type(self).instance is self:
            self._drop()
        super().close()

    def _deal(self) -> bool:
        self.run = model.Run(model.deal(self.rung, rng=self.rng))
        self.last_tick = self.clock()
        self.message = _('Push every crate onto a pad; keep clear of guards')
        self._drop()
        return True

    # --- controls ------------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase == self.PLAY and self.run is not None:
            model.apply(self.run, port)

    def _key(self, symbol: int, modifiers: int) -> None:
        moves = {key.UP: model.UP, key.DOWN: model.DOWN,
                 key.LEFT: model.LEFT, key.RIGHT: model.RIGHT,
                 key.W: model.UP, key.S: model.DOWN, key.A: model.LEFT,
                 key.D: model.RIGHT}
        if symbol in moves:
            self.steer(moves[symbol])

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
        if run.result is not None:
            self._judge(*run.result)
        else:
            self._redraw()

    # --- geometry ----------------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        room = self.run.floor.room
        left, bottom, width, height = self._area()
        head = height * 0.1
        s = min(width / room.width, (height - head) / room.height)
        x0 = left + (width - room.width * s) / 2
        return x0, bottom, s

    def _at(self, cell: int) -> Tuple[float, float]:
        room = self.run.floor.room
        x0, y0, s = self._frame()
        r, c = divmod(cell, room.width)
        return x0 + (c + 0.5) * s, y0 + (room.height - 1 - r + 0.5) * s

    # --- the warehouse, built once ---------------------------------------------------

    def _build_scenery(self) -> None:
        self._drop()
        run = self.run
        room = run.floor.room
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = room.width * s, room.height * s
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12, RACK_EDGE,
                    radius=12, shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        g2 = pyglet.graphics.Group(order=-12)
        draw = random.Random(room.player * 7 + len(room.walls))
        stock = ((236, 120, 60), (90, 170, 230), (130, 200, 100),
                 (240, 200, 70), (200, 110, 190))
        for cell in range(room.width * room.height):
            cx, cy = self._at(cell)
            x, y = cx - s / 2, cy - s / 2
            if cell in room.walls:
                out.append(pyglet.shapes.Rectangle(x, y, s + 0.5, s + 0.5,
                                                   color=RACK, batch=batch,
                                                   group=g0))
                # A shelf of stock.
                for k in range(2):
                    sy = y + s * (0.12 + 0.44 * k)
                    out.append(pyglet.shapes.Rectangle(
                        x + s * 0.06, sy, s * 0.88, s * 0.06,
                        color=RACK_EDGE, batch=batch, group=g1))
                    bx = x + s * 0.1
                    while bx < x + s * 0.85:
                        bw = s * draw.uniform(0.14, 0.26)
                        out.append(pyglet.shapes.Rectangle(
                            bx, sy + s * 0.06, min(bw, x + s * 0.9 - bx),
                            s * draw.uniform(0.16, 0.3),
                            color=polish.mix(draw.choice(stock), RACK, 0.35),
                            batch=batch, group=g1))
                        bx += bw + s * 0.03
                continue
            tone = polish.mix(CONCRETE, (255, 255, 255) if draw.random() < .5
                              else (0, 0, 0), draw.uniform(0, 0.05))
            out.append(pyglet.shapes.Rectangle(x, y, s + 0.5, s + 0.5,
                                               color=tone, batch=batch,
                                               group=g0))
            out.append(pyglet.shapes.Box(x, y, s, s, thickness=1,
                                         color=SEAM, batch=batch, group=g1))
            # Hazard stripes where the floor meets a rack below.
            if cell + room.width in room.walls:
                for k in range(5):
                    out.append(pyglet.shapes.Rectangle(
                        x + k * s * 0.2, y, s * 0.1, s * 0.07,
                        color=(240, 190, 40), batch=batch, group=g2))
            if cell in room.goals:
                out.append(pyglet.shapes.Circle(cx, cy, s * 0.36,
                                                color=polish.mix(PAD, tone,
                                                                 0.6),
                                                batch=batch, group=g1))
                out.append(pyglet.shapes.Arc(cx, cy, s * 0.36,
                                             thickness=max(2.0, s * 0.06),
                                             color=PAD, batch=batch,
                                             group=g2))
                for sgn in (-1, 1):
                    out.append(pyglet.shapes.Line(
                        cx - s * 0.16, cy - sgn * s * 0.16, cx + s * 0.16,
                        cy + sgn * s * 0.16, thickness=max(2.0, s * 0.05),
                        color=PAD, batch=batch, group=g2))
        # Patrol aisles, faintly painted.
        for p in run.floor.patrols:
            a, b = self._at(p.cells[0]), self._at(p.cells[-1])
            out.append(pyglet.shapes.Line(a[0], a[1], b[0], b[1],
                                          thickness=max(2.0, s * 0.12),
                                          color=(230, 120, 130, 70),
                                          batch=batch, group=g2))
        self.scenery_key = (id(self.batch), id(run.floor), self._frame())

    # --- each frame ---------------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        room = run.floor.room
        if self.scenery_key != (id(self.batch), id(run.floor), self._frame()):
            self._build_scenery()
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        t = run.t
        # Shutters.
        for sh in run.floor.shutters:
            cx, cy = self._at(sh.cell)
            shut = sh.cell in run.shut_now
            into = (t + sh.phase) % sh.period
            opening = sh.open_share * sh.period
            left_s = (opening - into) if into < opening else (sh.period - into)
            span = sh.period * (sh.open_share if into < opening
                                else 1 - sh.open_share)
            if shut:
                for k in range(5):
                    d.append(pyglet.shapes.Rectangle(
                        cx - s / 2, cy - s / 2 + k * s * 0.2, s, s * 0.16,
                        color=(120, 126, 140) if k % 2 else SHUTTER,
                        batch=batch, group=card))
            else:
                d.append(pyglet.shapes.Rectangle(
                    cx - s / 2, cy + s * 0.36, s, s * 0.14, color=SHUTTER,
                    batch=batch, group=card))
            d.append(pyglet.shapes.Arc(
                cx, cy, s * 0.3, thickness=max(2.0, s * 0.07),
                angle=360.0 * max(0.0, left_s / span), start_angle=90,
                color=(255, 90, 60) if not shut else (90, 220, 120),
                batch=batch, group=top))
        # Crates.
        for b in run.boxes:
            cx, cy = self._at(b)
            home = b in room.goals
            if home:
                polish.glow(d, batch, cx, cy, s * 0.75, CRATE_HOME,
                            strength=90, group=card)
            fill = CRATE_HOME if home else CRATE
            edge = polish.darker(fill, 0.3)
            m = s * 0.08
            d.append(pyglet.shapes.Rectangle(cx - s / 2 + m - 2,
                                             cy - s / 2 + m - 3, s - 2 * m,
                                             s - 2 * m, color=(30, 30, 40, 70),
                                             batch=batch, group=card))
            d.append(pyglet.shapes.Rectangle(cx - s / 2 + m, cy - s / 2 + m,
                                             s - 2 * m, s - 2 * m, color=fill,
                                             batch=batch, group=body))
            d.append(pyglet.shapes.Box(cx - s / 2 + m, cy - s / 2 + m,
                                       s - 2 * m, s - 2 * m,
                                       thickness=max(2.0, s * 0.08),
                                       color=edge, batch=batch, group=text))
            for sgn in (-1, 1):
                d.append(pyglet.shapes.Line(
                    cx - s * 0.3, cy - sgn * s * 0.3, cx + s * 0.3,
                    cy + sgn * s * 0.3, thickness=max(2.0, s * 0.07),
                    color=edge, batch=batch, group=text))
        # Guards: a beam the way they walk, a ring toward the next step.
        beat = run.floor.level.beat
        for g in run.guards:
            cx, cy = self._at(g.cell)
            k = g.k + g.heading
            if 0 <= k < len(g.cells):
                nx, ny = self._at(g.cells[k])
            else:
                nx, ny = cx, cy
            ux, uy = (nx - cx) / s, (ny - cy) / s
            px, py = -uy, ux
            reach = s * 1.6
            d.append(pyglet.shapes.Triangle(
                cx, cy, cx + ux * reach + px * s * 0.55,
                cy + uy * reach + py * s * 0.55,
                cx + ux * reach - px * s * 0.55,
                cy + uy * reach - py * s * 0.55,
                color=(255, 236, 140, 80), batch=batch, group=card))
            if (nx, ny) != (cx, cy):
                d.append(pyglet.shapes.Box(nx - s * 0.4, ny - s * 0.4,
                                           s * 0.8, s * 0.8, thickness=2,
                                           color=(255, 110, 110, 160),
                                           batch=batch, group=card))
            polish.glow(d, batch, cx, cy, s * 0.7, GUARD, strength=70,
                        group=card)
            d.append(pyglet.shapes.RoundedRectangle(
                cx - s * 0.32, cy - s * 0.32, s * 0.64, s * 0.64,
                radius=s * 0.14, color=GUARD, batch=batch, group=body))
            d.append(pyglet.shapes.RoundedRectangle(
                cx - s * 0.24 + ux * s * 0.06, cy + s * 0.02 + uy * s * 0.06,
                s * 0.48, s * 0.16, radius=s * 0.06, color=(40, 20, 30),
                batch=batch, group=text))
            d.append(pyglet.shapes.Circle(
                cx + ux * s * 0.16, cy + s * 0.1 + uy * s * 0.06, s * 0.06,
                color=(120, 240, 255), batch=batch, group=top))
            share = 1.0 - max(0.0, g.next_beat - t) / beat
            d.append(pyglet.shapes.Arc(cx, cy, s * 0.46, thickness=2,
                                       angle=360.0 * min(1.0, share),
                                       start_angle=90,
                                       color=(255, 200, 200), batch=batch,
                                       group=top))
        # The worker.
        cx, cy = self._at(run.player)
        ux, uy = ((0, 1), (0, -1), (-1, 0), (1, 0))[run.facing]
        polish.glow(d, batch, cx, cy, s * 0.7, HAT, strength=60, group=card)
        d.append(pyglet.shapes.Circle(cx, cy - s * 0.04, s * 0.3, color=VEST,
                                      batch=batch, group=body))
        d.append(pyglet.shapes.Rectangle(cx - s * 0.3, cy - s * 0.1,
                                         s * 0.6, s * 0.08,
                                         color=(250, 250, 220), batch=batch,
                                         group=text))
        d.append(pyglet.shapes.Circle(cx + ux * s * 0.08,
                                      cy + s * 0.08 + uy * s * 0.08,
                                      s * 0.2, color=HAT, batch=batch,
                                      group=top))
        d.append(pyglet.shapes.Circle(cx + ux * s * 0.24, cy + uy * s * 0.24,
                                      s * 0.06, color=(60, 40, 20),
                                      batch=batch, group=top))
        ready = max(0.0, run.ready_at - t)
        if ready > 0:
            d.append(pyglet.shapes.Arc(cx, cy, s * 0.44, thickness=2,
                                       angle=360.0 * (1 - ready / model.STEP),
                                       start_angle=90, color=HAT,
                                       batch=batch, group=top))
        # Along the top: pads covered and the time left.
        top_y = y0 + room.height * s
        W = room.width * s
        bar_h = s * 0.36
        by = top_y + s * 0.3
        covered = len(run.boxes & set(room.goals))
        n = len(room.goals)
        for k in range(n):
            gx = x0 + s * 0.3 + k * bar_h * 1.3
            d.append(pyglet.shapes.Circle(gx + bar_h / 2, by + bar_h / 2,
                                          bar_h * 0.5,
                                          color=CRATE_HOME if k < covered
                                          else (120, 130, 140),
                                          batch=batch, group=body))
        share = max(0.0, 1.0 - t / run.floor.seconds)
        bx = x0 + W * 0.35
        bw = W * 0.65 - s * 0.3
        polish.rounded(d, batch, bx, by, bw, bar_h, (90, 96, 110),
                       radius=bar_h / 2, group=card)
        if share > 0.02:
            polish.rounded(d, batch, bx, by, bw * share, bar_h,
                           polish.mix((240, 90, 70), (70, 200, 140),
                                      min(1.0, share * 1.6)),
                           radius=bar_h / 2, group=body)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        left = max(0, int(self.run.floor.seconds - self.run.t))
        return _('rung %d  %d/%d   %d s left   pushes %d') % (
            self.rung, self.trial, self.total_trials, left, self.run.pushes)
