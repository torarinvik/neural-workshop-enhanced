# -*- coding: utf-8 -*-
"""Firebreak on screen: a painted landscape, a fire, and a crew.

Arrows move the crew's cursor (Shift moves it four cells); Space or
Enter digs a break there; a click moves the cursor and digs. Forest is
dark green with trees, grass pale, water blue, rock grey, the town a
cluster of roofs. Burning cells flicker and smoke; the smoke drifts
with the wind, which from rung 16 is the only sign of it. Dug breaks
are furrowed earth; burned land is ash with dying embers.

For the agent boundary: ports 0-3 move the cursor up, down, left and
right, 4 digs, 5-8 move it four cells.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import firebreak as model
from ..i18n import _
from . import polish
from .rungtask import RungTask

GROUND = {model.FOREST: (58, 108, 60), model.GRASS: (152, 190, 92),
          model.WATER: (66, 136, 206), model.ROCK: (138, 134, 128),
          model.TOWN: (222, 206, 170), model.BREAK: (126, 92, 60)}
ROOFS = ((204, 82, 62), (82, 112, 172), (212, 162, 62), (150, 90, 150))
INK = (240, 242, 248, 255)


class Firebreak(RungTask):
    """Save the town."""

    instance: Optional['Firebreak'] = None

    TITLE = 'Firebreak'
    TASK_ID = 'firebreak'
    PREFIX = 'FIREBREAK'
    CATEGORY = 'decisions'
    FEEDBACK = 3.0
    FOOTNOTE = _('arrows move (Shift: four)   Space or Enter: dig   '
                 'click: dig there   Esc: menu')

    def __init__(self) -> None:
        self.blaze: Optional[model.Blaze] = None
        self.last_tick = 0.0
        self.scenery: List[object] = []
        self.scenery_key = None
        self.overlay: Dict[int, Tuple[str, List[object]]] = {}
        super().__init__()

    def _drop(self) -> None:
        for item in self.scenery:
            try:
                item.delete()
            except Exception:
                pass
        for _k, shapes in self.overlay.values():
            for item in shapes:
                try:
                    item.delete()
                except Exception:
                    pass
        self.scenery = []
        self.overlay = {}
        self.scenery_key = None

    def _clear_trial(self) -> None:
        self.blaze = None
        self._drop()

    def close(self) -> None:
        if type(self).instance is self:
            self._drop()
        super().close()

    def _deal(self) -> bool:
        self.blaze = model.Blaze(model.deal(self.rung, rng=self.rng))
        self.last_tick = self.clock()
        self.message = _('Cut firebreaks and save the town')
        self._drop()
        return True

    # --- controls ----------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase == self.PLAY and self.blaze is not None:
            model.apply(self.blaze, port)

    def _key(self, symbol: int, modifiers: int) -> None:
        moves = {key.UP: model.UP, key.DOWN: model.DOWN,
                 key.LEFT: model.LEFT, key.RIGHT: model.RIGHT}
        if symbol in moves:
            port = moves[symbol]
            if modifiers & key.MOD_SHIFT:
                port += model.JUMP
            self.steer(port)
        elif symbol in (key.SPACE, key.ENTER, key.RETURN):
            self.steer(model.DIG)

    def _click(self, x: float, y: float, button: int) -> None:
        if self.blaze is None:
            return
        x0, y0, s = self._frame()
        c, r = int((x - x0) // s), int((y - y0) // s)
        if 0 <= c < model.COLS and 0 <= r < model.ROWS:
            self.blaze.put(c, r)
            self.blaze.dig()

    def _tick(self) -> None:
        now = self.clock()
        dt = max(0.0, min(0.1, now - self.last_tick))
        self.last_tick = now
        self.blaze.step(dt)
        if self.blaze.result is not None:
            self._judge(*self.blaze.result)
        else:
            self._redraw()

    # --- geometry ------------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        head = height * 0.07
        s = min(width / model.COLS, (height - head) / model.ROWS)
        x0 = left + (width - model.COLS * s) / 2
        return x0, bottom, s

    def _centre(self, i: int) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        c, r = model.colrow(i)
        return x0 + (c + 0.5) * s, y0 + (r + 0.5) * s

    # --- the land, drawn once --------------------------------------------------

    def _build_scenery(self) -> None:
        self._drop()
        land = self.blaze.land
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.COLS * s, model.ROWS * s
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12,
                    (64, 74, 52), radius=14, shade=pal.shadow,
                    group=polish.STAGE)
        base_g = pyglet.graphics.Group(order=-14)
        deco_g = pyglet.graphics.Group(order=-13)
        top_g = pyglet.graphics.Group(order=-12)
        draw = random.Random(land.terrain.count(model.FOREST))
        for i, t in enumerate(land.terrain):
            c, r = model.colrow(i)
            x, y = x0 + c * s, y0 + r * s
            tint = draw.uniform(-0.06, 0.06)
            ground = polish.mix(GROUND[t], (255, 255, 255) if tint > 0
                                else (0, 0, 0), abs(tint))
            out.append(pyglet.shapes.Rectangle(x, y, s + 0.5, s + 0.5,
                                               color=ground, batch=batch,
                                               group=base_g))
            if t == model.FOREST:
                for _k in range(3):
                    tx = x + draw.uniform(0.2, 0.8) * s
                    ty = y + draw.uniform(0.2, 0.8) * s
                    rr = s * draw.uniform(0.2, 0.3)
                    leaf = polish.mix((40, 92, 48), (70, 134, 72),
                                      draw.random())
                    out.append(pyglet.shapes.Circle(
                        tx, ty, rr, color=leaf, batch=batch, group=deco_g))
                    out.append(pyglet.shapes.Circle(
                        tx - rr * 0.3, ty + rr * 0.3, rr * 0.4,
                        color=polish.lighter(leaf, 0.2), batch=batch,
                        group=top_g))
            elif t == model.GRASS:
                for _k in range(3):
                    tx = x + draw.uniform(0.15, 0.85) * s
                    ty = y + draw.uniform(0.15, 0.75) * s
                    out.append(pyglet.shapes.Line(
                        tx, ty, tx + s * 0.06, ty + s * 0.18,
                        thickness=max(1.0, s * 0.05),
                        color=(116, 156, 66), batch=batch, group=deco_g))
            elif t == model.WATER:
                ty = y + draw.uniform(0.3, 0.7) * s
                out.append(pyglet.shapes.Line(
                    x + s * 0.2, ty, x + s * 0.6, ty,
                    thickness=max(1.0, s * 0.06), color=(130, 186, 236),
                    batch=batch, group=deco_g))
            elif t == model.ROCK:
                for _k in range(2):
                    out.append(pyglet.shapes.Ellipse(
                        x + draw.uniform(0.25, 0.75) * s,
                        y + draw.uniform(0.3, 0.7) * s,
                        s * draw.uniform(0.12, 0.22), s * 0.12,
                        color=(172, 166, 160), batch=batch, group=deco_g))
            elif t == model.TOWN:
                roof = ROOFS[i % len(ROOFS)]
                bx, by = x + s * 0.2, y + s * 0.15
                out.append(pyglet.shapes.Rectangle(
                    bx, by, s * 0.6, s * 0.42, color=(244, 236, 218),
                    batch=batch, group=deco_g))
                out.append(pyglet.shapes.Triangle(
                    bx - s * 0.08, by + s * 0.42, bx + s * 0.68,
                    by + s * 0.42, bx + s * 0.3, by + s * 0.78, color=roof,
                    batch=batch, group=top_g))
                out.append(pyglet.shapes.Rectangle(
                    bx + s * 0.24, by, s * 0.12, s * 0.2,
                    color=(120, 84, 60), batch=batch, group=top_g))
        self.scenery_key = (id(self.batch), id(land), self._frame())

    # --- each frame --------------------------------------------------------------

    def _cell_art(self, i: int, kind: str) -> List[object]:
        x0, y0, s = self._frame()
        c, r = model.colrow(i)
        x, y = x0 + c * s, y0 + r * s
        batch = self.batch
        art: List[object] = []
        if kind == 'break':
            art.append(pyglet.shapes.Rectangle(
                x, y, s + 0.5, s + 0.5, color=GROUND[model.BREAK],
                batch=batch, group=self.card_group))
            for k in range(3):
                fy = y + s * (0.25 + 0.25 * k)
                art.append(pyglet.shapes.Line(
                    x + s * 0.12, fy, x + s * 0.88, fy,
                    thickness=max(1.0, s * 0.07), color=(98, 70, 46),
                    batch=batch, group=self.body_group))
        elif kind == 'burning':
            art.append(pyglet.shapes.Rectangle(
                x, y, s + 0.5, s + 0.5, color=(126, 44, 22),
                batch=batch, group=self.card_group))
            for k in range(3):
                art.append(pyglet.shapes.Triangle(
                    0, 0, 0, 0, 0, 0, color=(255, 120, 30),
                    batch=batch, group=self.body_group))
            art.append(pyglet.shapes.Circle(
                x + s / 2, y + s * 0.35, s * 0.18, color=(255, 226, 110),
                batch=batch, group=self.text_group))
            for k in range(2):
                art.append(pyglet.shapes.Circle(
                    0, 0, s * 0.3, color=(90, 90, 96, 90), batch=batch,
                    group=self.top_group))
        elif kind == 'ash':
            art.append(pyglet.shapes.Rectangle(
                x, y, s + 0.5, s + 0.5, color=(64, 60, 58),
                batch=batch, group=self.card_group))
            art.append(pyglet.shapes.Circle(
                x + s * 0.4, y + s * 0.45, s * 0.1, color=(220, 90, 40),
                batch=batch, group=self.body_group))
        return art

    def _sync_cells(self) -> None:
        blaze = self.blaze
        s = self._frame()[2]
        t = blaze.t
        wx, wy = blaze.wind()
        for i in range(model.COLS * model.ROWS):
            st = blaze.state[i]
            if st == model.BURNING:
                kind = 'burning'
            elif st == model.ASH:
                kind = 'ash'
            elif blaze.terrain[i] == model.BREAK:
                kind = 'break'
            else:
                kind = ''
            have = self.overlay.get(i)
            if (have[0] if have else '') != kind:
                if have:
                    for item in have[1]:
                        item.delete()
                if kind:
                    self.overlay[i] = (kind, self._cell_art(i, kind))
                else:
                    self.overlay.pop(i, None)
            if kind == 'burning':
                art = self.overlay[i][1]
                cx, cy = self._centre(i)
                age = t - blaze.lit_at[i]
                life = model.BURN[blaze.terrain[i]]
                fade = max(0.25, 1.0 - age / life)
                for k in range(3):
                    flick = 0.75 + 0.35 * math.sin(t * 13 + i * 1.7 + k * 2)
                    w = s * 0.22 * fade
                    h = s * 0.62 * fade * flick
                    fx = cx + (k - 1) * s * 0.24
                    tri = art[1 + k]
                    tri.x, tri.y = fx - w, cy - s * 0.38
                    tri.x2, tri.y2 = fx + w, cy - s * 0.38
                    tri.x3, tri.y3 = fx + wx * s * 0.15, cy - s * 0.38 + h
                    tri.color = (255, int(110 + 60 * flick * fade), 30)
                core = art[4]
                core.radius = s * 0.18 * fade * (0.8 + 0.3 * math.sin(
                    t * 17 + i))
                art[0].color = polish.mix((168, 58, 22), (82, 34, 22),
                                          1.0 - fade)
                top = self._frame()[1] + model.ROWS * s
                for k in range(2):
                    puff = art[5 + k]
                    phase = (t * 0.5 + k * 0.5 + i * 0.37) % 1.0
                    puff.x = cx + wx * s * 2.0 * phase + math.sin(
                        t + i) * s * 0.1
                    puff.y = min(top - s * 0.3, cy + s * 0.3 + wy * s * 2.0
                                 * phase + phase * s * 0.5)
                    puff.radius = s * (0.15 + 0.3 * phase)
                    puff.opacity = int(70 * (1 - phase) * fade)
            elif kind == 'ash':
                ember = self.overlay[i][1][1]
                age = t - blaze.lit_at[i] - model.BURN.get(
                    self.blaze.land.terrain[i], 5.0)
                ember.opacity = max(0, int(255 - age * 40))

    def _draw(self, left, bottom, width, height) -> None:
        blaze = self.blaze
        if self.scenery_key != (id(self.batch), id(blaze.land),
                                self._frame()):
            self._build_scenery()
        self._sync_cells()
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        top = y0 + model.ROWS * s
        # The cursor: white when the crew is ready, amber while it digs.
        c, r = blaze.cursor
        ready = blaze.t >= blaze.ready_at and blaze.shovels > 0
        colour = (255, 255, 255) if ready else (255, 190, 60)
        pulse = 1.0 + 0.08 * math.sin(blaze.t * 8)
        cx, cy = x0 + (c + 0.5) * s, y0 + (r + 0.5) * s
        half = s * 0.55 * pulse
        d.append(pyglet.shapes.Box(cx - half, cy - half, half * 2, half * 2,
                                   thickness=max(2.0, s * 0.1),
                                   color=colour, batch=batch,
                                   group=pyglet.graphics.Group(order=6)))
        if not ready and blaze.shovels > 0:
            share = 1.0 - (blaze.ready_at - blaze.t) / blaze.land.level.dig
            d.append(pyglet.shapes.Arc(cx, cy, s * 0.8, thickness=3,
                                       angle=360.0 * max(0.0, share),
                                       start_angle=90.0, color=colour,
                                       batch=batch,
                                       group=pyglet.graphics.Group(order=6)))
        # Along the top: shovels, burned, the wind.
        size = max(9.0, s * 0.42)
        polish.rounded(d, batch, x0, top + s * 0.25, model.COLS * s,
                       s * 1.1, (40, 46, 40, 220), radius=s * 0.3,
                       group=self.card_group)
        ty = top + s * 0.8
        self._text(_('shovels %d') % blaze.shovels, x0 + s * 0.6, ty, size,
                   anchor='left', bold=True, colour=INK)
        burning = sum(1 for st in blaze.state if st == model.BURNING)
        self._text(_('burning %d   burned %d') % (burning, blaze.burned()),
                   x0 + model.COLS * s * 0.45, ty, size, colour=INK)
        if not blaze.land.level.hidden_wind:
            wx, wy = blaze.wind()
            ax, ay = x0 + model.COLS * s - s * 2.2, ty
            n = math.hypot(wx, wy) or 1.0
            ux, uy = wx / n, wy / n
            tip = (ax + ux * s * 0.7, ay + uy * s * 0.25)
            tail = (ax - ux * s * 0.7, ay - uy * s * 0.25)
            sky = (160, 210, 255)
            d.append(pyglet.shapes.Line(tail[0], tail[1], tip[0], tip[1],
                                        thickness=3, color=sky,
                                        batch=batch, group=self.top_group))
            px, py = -uy, ux
            hs = s * 0.32
            d.append(pyglet.shapes.Triangle(
                tip[0] + ux * hs, tip[1] + uy * hs,
                tip[0] + px * hs * 0.7, tip[1] + py * hs * 0.7,
                tip[0] - px * hs * 0.7, tip[1] - py * hs * 0.7,
                color=sky, batch=batch, group=self.top_group))
            self._text(_('wind'), ax - s * 1.5, ty, size * 0.9,
                       anchor='right', colour=sky + (255,))

    def _facts(self) -> str:
        if self.blaze is None:
            return ''
        return _('rung %d  %d/%d   %d s') % (self.rung, self.trial,
                                             self.total_trials,
                                             int(self.blaze.t))
