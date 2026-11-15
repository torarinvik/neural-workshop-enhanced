# -*- coding: utf-8 -*-
"""Kitchen on screen: a tiled kitchen, a cook, and tickets on the rail.

Each station wears its key: crates 1-4, boards Q W, stoves E R T,
plates A S, the pass D and the bin F; a click on a station sends the
cook there too. Food is drawn whole when raw, in pieces once chopped,
browned when cooked and black when burnt. A pan's ring fills green
while it cooks, turns gold when it is done and red as it nears
burning. Tickets hang along the top with their parts -- a knife for
chopped, a flame for cooked -- and a bar for the patience left.

For the agent boundary: ports 0-12 send the cook to the stations in
that order (crates, boards, stoves, plates, pass, bin).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import kitchen as model
from ..i18n import _
from . import polish
from .rungtask import RungTask

KEYS = (key._1, key._2, key._3, key._4, key.Q, key.W, key.E, key.R, key.T,
        key.A, key.S, key.D, key.F)
KEY_NAMES = '1234QWERTASDF'
FOOD = {'tomato': (230, 64, 52), 'onion': (156, 92, 196),
        'mushroom': (198, 160, 118), 'fish': (90, 156, 226)}
TILE_A = (244, 232, 210)
TILE_B = (226, 206, 178)
COUNTER = (150, 104, 66)
COUNTER_TOP = (186, 138, 92)
STEEL = (176, 184, 196)
INK = (40, 32, 28, 255)


class Kitchen(RungTask):
    """Serve every ticket before its patience runs out."""

    instance: Optional['Kitchen'] = None

    TITLE = 'Kitchen'
    TASK_ID = 'kitchen'
    PREFIX = 'KITCHEN'
    CATEGORY = 'planning'
    FEEDBACK = 3.0
    FOOTNOTE = _('crates 1-4  boards Q W  stoves E R T  plates A S  '
                 'pass D  bin F  (or click)   Esc: menu')

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
        self.message = _('Cook and plate every ticket before it lapses')
        self._drop()
        return True

    # --- controls -------------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase == self.PLAY and self.run is not None:
            model.apply(self.run, port)

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in KEYS:
            self.steer(KEYS.index(symbol))

    def _click(self, x: float, y: float, button: int) -> None:
        if self.run is None:
            return
        s = self._frame()[2]
        best, port = (1.0 * s) ** 2, None
        for st in self.run.shift.stations:
            px, py = self._at(st.x, st.y)
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best:
                best, port = d, st.port
        if port is not None:
            self.steer(port)

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

    # --- geometry ---------------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        rail = height * 0.2
        s = min(width / model.W, (height - rail) / model.H)
        x0 = left + (width - model.W * s) / 2
        return x0, bottom, s

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    # --- drawing helpers ----------------------------------------------------------

    def _food(self, out, x: float, y: float, r: float, food: str, stage: str,
              group) -> None:
        batch = self.batch
        base = FOOD[food]
        if stage == model.COOKED:
            base = polish.mix(base, (120, 70, 30), 0.35)
        elif stage == model.BURNT:
            base = (40, 34, 32)
        if stage in (model.CHOPPED, model.COOKED, model.BURNT):
            for k, (dx, dy) in enumerate(((-0.4, -0.2), (0.4, -0.25),
                                          (0.0, 0.35))):
                out.append(pyglet.shapes.Circle(
                    x + dx * r, y + dy * r, r * 0.45,
                    color=polish.lighter(base, 0.08 * k), batch=batch,
                    group=group))
            return
        if food == 'tomato':
            out.append(pyglet.shapes.Circle(x, y, r, color=base, batch=batch,
                                            group=group))
            out.append(pyglet.shapes.Circle(x - r * 0.3, y + r * 0.3,
                                            r * 0.22,
                                            color=polish.lighter(base, 0.4),
                                            batch=batch, group=group))
            out.append(pyglet.shapes.Triangle(
                x - r * 0.3, y + r * 0.9, x + r * 0.3, y + r * 0.9, x,
                y + r * 1.3, color=(70, 160, 70), batch=batch, group=group))
        elif food == 'onion':
            out.append(pyglet.shapes.Circle(x, y - r * 0.1, r * 0.9,
                                            color=base, batch=batch,
                                            group=group))
            out.append(pyglet.shapes.Triangle(
                x - r * 0.45, y + r * 0.5, x + r * 0.45, y + r * 0.5, x,
                y + r * 1.3, color=base, batch=batch, group=group))
        elif food == 'mushroom':
            out.append(pyglet.shapes.Rectangle(x - r * 0.25, y - r, r * 0.5,
                                               r, color=(240, 228, 206),
                                               batch=batch, group=group))
            out.append(pyglet.shapes.Sector(x, y - r * 0.1, r, angle=180,
                                            start_angle=0, color=base,
                                            batch=batch, group=group))
        else:
            out.append(pyglet.shapes.Ellipse(x, y, r * 1.1, r * 0.6,
                                             color=base, batch=batch,
                                             group=group))
            out.append(pyglet.shapes.Triangle(
                x + r * 0.9, y, x + r * 1.5, y + r * 0.5, x + r * 1.5,
                y - r * 0.5, color=base, batch=batch, group=group))
            out.append(pyglet.shapes.Circle(x - r * 0.6, y + r * 0.1,
                                            r * 0.12, color=(20, 20, 30),
                                            batch=batch, group=group))

    def _stage_mark(self, out, x, y, r, stage, group) -> None:
        batch = self.batch
        if stage == model.CHOPPED:
            out.append(pyglet.shapes.Line(x - r, y - r, x + r, y + r,
                                          thickness=max(2.0, r * 0.3),
                                          color=(150, 160, 175), batch=batch,
                                          group=group))
            out.append(pyglet.shapes.Line(x - r, y - r, x - r * 0.4,
                                          y - r * 0.4,
                                          thickness=max(2.5, r * 0.45),
                                          color=(110, 70, 40), batch=batch,
                                          group=group))
        else:
            out.append(pyglet.shapes.Triangle(
                x - r * 0.7, y - r * 0.8, x + r * 0.7, y - r * 0.8, x,
                y + r, color=(255, 120, 40), batch=batch, group=group))
            out.append(pyglet.shapes.Triangle(
                x - r * 0.35, y - r * 0.8, x + r * 0.35, y - r * 0.8, x,
                y + r * 0.3, color=(255, 220, 90), batch=batch, group=group))

    # --- the room, built once --------------------------------------------------------

    def _build_scenery(self) -> None:
        self._drop()
        run = self.run
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.W * s, model.H * s
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12, COUNTER,
                    radius=12, shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        tile = s * 0.75
        cols, rows = int(W / tile) + 1, int(H / tile) + 1
        for c in range(cols):
            for r in range(rows):
                w = min(tile, W - c * tile)
                h = min(tile, H - r * tile)
                if w <= 0 or h <= 0:
                    continue
                out.append(pyglet.shapes.Rectangle(
                    x0 + c * tile, y0 + r * tile, w, h,
                    color=TILE_A if (c + r) % 2 else TILE_B, batch=batch,
                    group=g0))
        # Counters under each station.
        for st in run.shift.stations:
            px, py = self._at(st.x, st.y)
            out.append(pyglet.shapes.RoundedRectangle(
                px - s * 0.62, py - s * 0.62, s * 1.24, s * 1.24,
                radius=s * 0.12, color=COUNTER, batch=batch, group=g1))
            out.append(pyglet.shapes.RoundedRectangle(
                px - s * 0.56, py - s * 0.52, s * 1.12, s * 1.1,
                radius=s * 0.1, color=COUNTER_TOP if st.kind not in (
                    model.STOVE, model.PASS) else (70, 72, 80),
                batch=batch, group=g1))
        self.scenery_key = (id(self.batch), id(run.shift), self._frame())

    # --- each frame -----------------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if self.scenery_key != (id(self.batch), id(run.shift), self._frame()):
            self._build_scenery()
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        t = run.t
        for st in run.shift.stations:
            px, py = self._at(st.x, st.y)
            if st.kind == model.CRATE:
                d.append(pyglet.shapes.Rectangle(px - s * 0.45, py - s * 0.4,
                                                 s * 0.9, s * 0.62,
                                                 color=(168, 120, 70),
                                                 batch=batch, group=card))
                for k in range(3):
                    d.append(pyglet.shapes.Line(
                        px - s * 0.45, py - s * 0.4 + k * s * 0.2,
                        px + s * 0.45, py - s * 0.4 + k * s * 0.2,
                        thickness=2, color=(130, 88, 50), batch=batch,
                        group=body))
                for k, dx in enumerate((-0.22, 0.22, 0.0)):
                    self._food(d, px + dx * s, py + s * (0.24 + 0.12 * (
                        k == 2)), s * 0.18, st.food, model.RAW, text)
            elif st.kind == model.BOARD:
                d.append(pyglet.shapes.RoundedRectangle(
                    px - s * 0.42, py - s * 0.3, s * 0.84, s * 0.6,
                    radius=s * 0.08, color=(222, 180, 120), batch=batch,
                    group=card))
                board = run.boards[st.index]
                if board is not None:
                    done = board[1] >= model.CHOP
                    self._food(d, px, py, s * 0.2, board[0],
                               model.CHOPPED if done else model.RAW, body)
                    share = min(1.0, board[1] / model.CHOP)
                    d.append(pyglet.shapes.Arc(
                        px, py, s * 0.5, thickness=max(3.0, s * 0.07),
                        angle=360 * share, start_angle=90,
                        color=(90, 200, 255) if not done else (120, 230, 140),
                        batch=batch, group=top))
                    if run.chopping == st.index:
                        a = math.sin(t * 18) * 0.5
                        d.append(pyglet.shapes.Line(
                            px + s * 0.1, py + s * 0.3,
                            px + s * (0.1 + 0.4 * math.cos(a)),
                            py + s * (0.3 + 0.2 * math.sin(a)),
                            thickness=max(3.0, s * 0.07),
                            color=(200, 206, 216), batch=batch, group=top))
            elif st.kind == model.STOVE:
                pan = run.stoves[st.index]
                lit = pan is not None
                if lit:
                    polish.glow(d, batch, px, py, s * 0.65, (255, 120, 40),
                                strength=80, group=card)
                d.append(pyglet.shapes.Arc(px, py, s * 0.4,
                                           thickness=max(2.0, s * 0.06),
                                           color=(255, 110, 40) if lit
                                           else (60, 60, 66), batch=batch,
                                           group=card))
                d.append(pyglet.shapes.Circle(px, py, s * 0.32,
                                              color=(46, 46, 52),
                                              batch=batch, group=body))
                d.append(pyglet.shapes.Line(px + s * 0.3, py, px + s * 0.6,
                                            py - s * 0.08,
                                            thickness=max(3.0, s * 0.08),
                                            color=(46, 46, 52), batch=batch,
                                            group=body))
                if lit:
                    stage = run.pan_stage(st.index)
                    shown = model.RAW if stage == model.CHOPPED else stage
                    self._food(d, px, py, s * 0.18, pan.food,
                               model.CHOPPED if shown == model.RAW else shown,
                               text)
                    age = t - pan.since
                    if stage == model.CHOPPED:
                        share, colour = age / model.COOK, (110, 220, 120)
                    elif stage == model.COOKED:
                        left_s = model.COOK + run.level.hold - age
                        share = left_s / run.level.hold
                        pulse = 0.5 + 0.5 * math.sin(t * (8 + 12 * (
                            1 - share)))
                        colour = polish.mix((255, 210, 60), (255, 60, 50),
                                            1 - share)
                        colour = polish.mix(colour, (255, 255, 255),
                                            0.3 * pulse)
                    else:
                        share, colour = 1.0, (60, 50, 50)
                    d.append(pyglet.shapes.Arc(
                        px, py, s * 0.52, thickness=max(3.0, s * 0.08),
                        angle=360 * max(0.0, min(1.0, share)),
                        start_angle=90, color=colour, batch=batch,
                        group=top))
                    # Steam, or smoke once it burns.
                    for k in range(3):
                        ph = (t * 0.7 + k / 3) % 1.0
                        smoke = stage == model.BURNT
                        d.append(pyglet.shapes.Circle(
                            px + math.sin(t * 2 + k * 2) * s * 0.12,
                            py + s * (0.3 + 0.7 * ph),
                            s * (0.08 + 0.12 * ph),
                            color=((60, 56, 56) if smoke
                                   else (250, 250, 250)) + (
                                int(150 * (1 - ph)),),
                            batch=batch, group=top))
            elif st.kind == model.PLATE:
                d.append(pyglet.shapes.Circle(px, py, s * 0.42,
                                              color=(250, 250, 252),
                                              batch=batch, group=card))
                d.append(pyglet.shapes.Arc(px, py, s * 0.32, thickness=2,
                                           color=(214, 220, 232),
                                           batch=batch, group=body))
                plate = run.plates[st.index]
                for k, (food, stage) in enumerate(plate):
                    a = math.radians(90 + k * 120)
                    off = s * 0.17 if len(plate) > 1 else 0.0
                    self._food(d, px + math.cos(a) * off,
                               py + math.sin(a) * off, s * 0.13, food,
                               stage, text)
            elif st.kind == model.PASS:
                d.append(pyglet.shapes.RoundedRectangle(
                    px - s * 0.45, py - s * 0.35, s * 0.9, s * 0.7,
                    radius=s * 0.08, color=STEEL, batch=batch, group=card))
                d.append(pyglet.shapes.Sector(px, py - s * 0.05, s * 0.22,
                                              angle=180, start_angle=0,
                                              color=(250, 200, 60),
                                              batch=batch, group=body))
                d.append(pyglet.shapes.Circle(px, py + s * 0.2, s * 0.05,
                                              color=(250, 200, 60),
                                              batch=batch, group=body))
            elif st.kind == model.BIN:
                d.append(pyglet.shapes.RoundedRectangle(
                    px - s * 0.28, py - s * 0.35, s * 0.56, s * 0.62,
                    radius=s * 0.06, color=(110, 118, 130), batch=batch,
                    group=card))
                d.append(pyglet.shapes.Rectangle(
                    px - s * 0.34, py + s * 0.24, s * 0.68, s * 0.1,
                    color=(80, 86, 98), batch=batch, group=body))
            # The station's key, on a cap.
            kx, ky = px - s * 0.5, py + s * 0.46
            d.append(pyglet.shapes.RoundedRectangle(
                kx - s * 0.16, ky - s * 0.16, s * 0.32, s * 0.32,
                radius=s * 0.06, color=(40, 36, 44), batch=batch,
                group=text))
            self._text(KEY_NAMES[st.port], kx, ky, max(7.0, s * 0.2),
                       bold=True, colour=(255, 255, 255, 255))
        # The cook.
        cx, cy = self._at(run.x, run.y)
        if run.target is not None:
            tx, ty = self._at(run.target.x, run.target.y)
            d.append(pyglet.shapes.Line(cx, cy, tx, ty, thickness=2,
                                        color=(90, 140, 230, 120),
                                        batch=batch, group=card))
            d.append(pyglet.shapes.Arc(tx, ty, s * 0.66, thickness=2,
                                       color=(90, 140, 230), batch=batch,
                                       group=top))
        bob = math.sin(t * 14) * s * 0.03 if run.target is not None else 0.0
        d.append(pyglet.shapes.Ellipse(cx, cy - s * 0.3, s * 0.3, s * 0.1,
                                       color=(60, 40, 30, 80), batch=batch,
                                       group=card))
        d.append(pyglet.shapes.Circle(cx, cy + bob, s * 0.3,
                                      color=(252, 252, 255), batch=batch,
                                      group=body))
        d.append(pyglet.shapes.Arc(cx, cy + bob, s * 0.3, thickness=2,
                                   color=(170, 176, 190), batch=batch,
                                   group=body))
        d.append(pyglet.shapes.Circle(cx, cy + s * 0.18 + bob, s * 0.16,
                                      color=(242, 200, 160), batch=batch,
                                      group=text))
        d.append(pyglet.shapes.RoundedRectangle(
            cx - s * 0.14, cy + s * 0.3 + bob, s * 0.28, s * 0.26,
            radius=s * 0.08, color=(255, 255, 255), batch=batch, group=top))
        held = run.held
        if held is not None:
            hx, hy = cx + s * 0.38, cy + s * 0.05 + bob
            if held[0] == 'plate':
                d.append(pyglet.shapes.Circle(hx, hy, s * 0.24,
                                              color=(250, 250, 252),
                                              batch=batch, group=top))
                for k, (food, stage) in enumerate(held[1]):
                    a = math.radians(90 + k * 120)
                    self._food(d, hx + math.cos(a) * s * 0.1,
                               hy + math.sin(a) * s * 0.1, s * 0.08, food,
                               stage, top)
            else:
                self._food(d, hx, hy, s * 0.14, held[0], held[1], top)
        # Notes that float up from the pass and the bin.
        for when, words, nx, ny in run.flash:
            age = t - when
            if age > 1.5:
                continue
            px, py = self._at(nx, ny)
            self._text(words, px - s * 0.4, py + s * (0.8 + age * 0.6),
                       max(9.0, s * 0.26), anchor='right', bold=True,
                       colour=(40, 140, 70, int(255 * (1 - age / 1.5))))
        # The rail of tickets.
        rail_y = y0 + model.H * s + s * 0.3
        rail_h = min(s * 1.7, bottom + height - rail_y - 4)
        tickets = run.shift.tickets
        cw = min(s * 2.4, (model.W * s) / 6.3)
        d.append(pyglet.shapes.Rectangle(x0, rail_y + rail_h - s * 0.08,
                                         model.W * s, s * 0.08,
                                         color=STEEL, batch=batch,
                                         group=card))
        for j, k in enumerate(sorted(run.open, key=lambda q: tickets[q].due)):
            tk = tickets[k]
            tx = x0 + j * (cw + s * 0.15)
            if tx + cw > x0 + model.W * s:
                break
            left_s = run.ticket_left(k)
            share = max(0.0, left_s / tk.patience)
            urgent = share < 0.3
            polish.card(d, batch, tx, rail_y, cw, rail_h - s * 0.1,
                        (255, 250, 236) if not urgent else
                        polish.mix((255, 250, 236), (255, 160, 150),
                                   0.5 + 0.5 * math.sin(t * 8)),
                        radius=6, lift=2, group=card)
            n = len(tk.parts)
            for q, (food, stage) in enumerate(tk.parts):
                fx = tx + cw * (q + 0.5) / n
                fy = rail_y + rail_h * 0.55
                self._food(d, fx, fy, min(s * 0.2, cw / (n * 3.2)), food,
                           model.RAW, text)
                self._stage_mark(d, fx + cw / (n * 4), fy - rail_h * 0.18,
                                 s * 0.1, stage, top)
            d.append(pyglet.shapes.Rectangle(
                tx + cw * 0.08, rail_y + rail_h * 0.08,
                cw * 0.84 * share, rail_h * 0.1,
                color=polish.mix((230, 70, 60), (70, 190, 110),
                                 min(1.0, share * 1.5)),
                batch=batch, group=body))
        waiting = len(tickets) - run.arrived
        self._text(_('%d to come') % waiting, x0 + model.W * s,
                   rail_y + rail_h * 0.45, max(9.0, s * 0.26),
                   anchor='right', bold=True, colour=(120, 110, 100, 255))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   served %d of %d   lapsed %d') % (
            self.rung, self.trial, self.total_trials, len(run.served),
            len(run.shift.tickets), len(run.lapsed))
