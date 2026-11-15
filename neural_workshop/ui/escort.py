# -*- coding: utf-8 -*-
"""Escort on screen: a torch-lit temple, its walkers and its levers.

Along the top, a lever for every number key: pull it (key 1-6 or a
click) and every device wearing its coloured gem flips. Doors are
portcullises that rise and fall; bridges are plank spans sliding over
black pits; flame jets hiss with sparks before they roar. Each walker
carries a lantern of its own colour; a walker held at a door shows a
pause mark. The east gate glows when someone is through.

For the agent boundary: ports 0-5 pull levers 1-6.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import escort as model
from ..i18n import _
from . import polish
from .rungtask import RungTask

LEVER_COLOURS = ((255, 200, 60), (64, 214, 200), (236, 92, 196),
                 (96, 160, 255), (156, 226, 78), (255, 136, 64))
WALKER_COLOURS = ((255, 236, 170), (170, 236, 255), (255, 186, 226))
WALL = (70, 58, 52)
WALL_LINE = (56, 46, 42)
FLOOR = (196, 170, 128)
PIT = (16, 12, 18)
PLANK = (150, 104, 62)
IRON = (82, 84, 96)
INK = (246, 238, 222, 255)


def lever_colour(k: int) -> Tuple[int, int, int]:
    return LEVER_COLOURS[k % len(LEVER_COLOURS)]


class Escort(RungTask):
    """Bring every walker through the temple."""

    instance: Optional['Escort'] = None

    TITLE = 'Escort'
    TASK_ID = 'escort'
    PREFIX = 'ESCORT'
    CATEGORY = 'planning'
    FEEDBACK = 3.0
    FOOTNOTE = _('1-6 or click: pull a lever   Esc: menu')

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        self.last_tick = 0.0
        self.flips: List[int] = []
        self.scenery: List[object] = []
        self.scenery_key = None
        self.trails: List[List[Tuple[float, float]]] = []
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
        temple = model.deal(self.rung, rng=self.rng)
        self.run = model.Run(temple)
        self.flips = [0] * len(temple.levers)
        self.trails = [[] for _p in temple.paths]
        self.last_tick = self.clock()
        self.message = _('Work the levers; bring every walker through')
        self._drop()
        return True

    # --- controls ----------------------------------------------------------

    def steer(self, port: int) -> None:
        run = self.run
        if self.phase != self.PLAY or run is None:
            return
        if 0 <= port < len(run.temple.levers):
            run.pull(port)
            self.flips[port] += 1

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._6:
            self.steer(symbol - key._1)

    def _click(self, x: float, y: float, button: int) -> None:
        if self.run is None:
            return
        for k in range(len(self.run.temple.levers)):
            lx, ly, lw, lh = self._lever_box(k)
            if lx <= x <= lx + lw and ly <= y <= ly + lh:
                self.steer(k)
                return
        x0, y0, s = self._frame()
        best, port = (0.8 * s) ** 2, None
        for i, d in enumerate(self.run.temple.devices):
            if d.lever is None:
                continue
            px, py = self._cell(*self.run.temple.paths[d.walker][d.at])
            dist = (px - x) ** 2 + (py - y) ** 2
            if dist < best:
                best, port = dist, d.lever
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
        for w, trail in enumerate(self.trails):
            here = run.where(w)
            if not trail or math.hypot(here[0] - trail[-1][0],
                                       here[1] - trail[-1][1]) > 0.5:
                trail.append(here)
                del trail[:-10]
        if run.result is not None:
            self._judge(*run.result)
        else:
            self._redraw()

    # --- geometry --------------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        panel = height * 0.2
        s = min(width / model.COLS, (height - panel) / model.ROWS)
        x0 = left + (width - model.COLS * s) / 2
        return x0, bottom, s

    def _cell(self, c: float, r: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + (c + 0.5) * s, y0 + (model.ROWS - 1 - r + 0.5) * s

    def _lever_box(self, k: int) -> Tuple[float, float, float, float]:
        x0, y0, s = self._frame()
        n = len(self.run.temple.levers)
        top = y0 + model.ROWS * s
        left, bottom, width, height = self._area()
        h = min(bottom + height - top, s * 3.2) - s * 0.5
        w = min(s * 3.4, (model.COLS * s) / max(n, 1) - s * 0.4)
        span = n * w + (n - 1) * s * 0.4
        x = x0 + (model.COLS * s - span) / 2 + k * (w + s * 0.4)
        return x, top + s * 0.4, w, h

    # --- the temple, built once ----------------------------------------------------

    def _build_scenery(self) -> None:
        self._drop()
        run = self.run
        temple = run.temple
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.COLS * s, model.ROWS * s
        polish.card(out, batch, x0 - 8, y0 - 8, W + 16, H + 16, (44, 36, 34),
                    radius=12, shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        g2 = pyglet.graphics.Group(order=-12)
        draw = random.Random(len(temple.devices) * 31 + len(temple.paths[0]))
        out.append(pyglet.shapes.Rectangle(x0, y0, W, H, color=WALL,
                                           batch=batch, group=g0))
        # Brick courses on the walls.
        for r in range(model.ROWS * 2):
            y = y0 + r * s / 2
            out.append(pyglet.shapes.Line(x0, y, x0 + W, y, thickness=1,
                                          color=WALL_LINE, batch=batch,
                                          group=g0))
            shift = (r % 2) * s * 0.5
            for c in range(model.COLS + 1):
                x = x0 + c * s + shift
                if x < x0 + W:
                    out.append(pyglet.shapes.Line(
                        x, y, x, y + s / 2, thickness=1, color=WALL_LINE,
                        batch=batch, group=g0))
        pits = {(temple.paths[d.walker][d.at]) for d in temple.devices
                if d.kind == model.BRIDGE}
        for w, path in enumerate(temple.paths):
            tint = WALKER_COLOURS[w % len(WALKER_COLOURS)]
            for k, (c, r) in enumerate(path):
                cx, cy = self._cell(c, r)
                if (c, r) in pits:
                    out.append(pyglet.shapes.Rectangle(
                        cx - s / 2, cy - s / 2, s, s, color=PIT, batch=batch,
                        group=g1))
                    for j in range(3):
                        out.append(pyglet.shapes.Rectangle(
                            cx - s / 2 + j * s * 0.08, cy - s / 2 + j * s * 0.08,
                            s - j * s * 0.16, s - j * s * 0.16,
                            color=polish.mix(PIT, (60, 30, 70), 0.3 - j * 0.1),
                            batch=batch, group=g1))
                    continue
                shade = polish.mix(FLOOR, tint, 0.12)
                shade = polish.mix(shade, (0, 0, 0), draw.uniform(0, 0.12))
                out.append(pyglet.shapes.Rectangle(
                    cx - s / 2, cy - s / 2, s, s, color=shade, batch=batch,
                    group=g1))
                out.append(pyglet.shapes.Box(
                    cx - s / 2, cy - s / 2, s, s, thickness=1,
                    color=polish.darker(shade, 0.18), batch=batch, group=g2))
                if draw.random() < 0.25:
                    out.append(pyglet.shapes.Line(
                        cx - s * 0.2, cy + s * 0.1, cx + s * 0.15,
                        cy - s * 0.15, thickness=1,
                        color=polish.darker(shade, 0.25), batch=batch,
                        group=g2))
            # Gates: an arch at each end.
            for (c, r), hue in ((path[0], (120, 110, 100)),
                                (path[-1], (250, 214, 120))):
                cx, cy = self._cell(c, r)
                out.append(pyglet.shapes.Arc(
                    cx, cy, s * 0.62, thickness=s * 0.14, angle=180,
                    start_angle=0 if c else 0, color=hue, batch=batch,
                    group=g2))
        # Jet nozzles in the floor.
        for d in temple.devices:
            if d.kind == model.JET:
                cx, cy = self._cell(*temple.paths[d.walker][d.at])
                out.append(pyglet.shapes.Circle(cx, cy, s * 0.3,
                                                color=(54, 50, 56),
                                                batch=batch, group=g2))
                out.append(pyglet.shapes.Circle(cx, cy, s * 0.16,
                                                color=(24, 20, 24),
                                                batch=batch, group=g2))
        # Torches: wall cells beside the path, a few of them.
        floor = {cell for path in temple.paths for cell in path}
        spots = []
        for path in temple.paths:
            for c, r in path[2::5]:
                for dr in (-1, 1):
                    if (c, r + dr) not in floor and 0 <= r + dr < model.ROWS:
                        spots.append((c, r + dr))
                        break
        self.torches = spots
        self.scenery_key = (id(self.batch), id(temple), self._frame())

    # --- each frame ----------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        temple = run.temple
        if self.scenery_key != (id(self.batch), id(temple), self._frame()):
            self._build_scenery()
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        t = run.t
        card, body, text, top = (self.card_group, self.body_group,
                                 self.text_group, self.top_group)
        # Torches flicker.
        for k, (c, r) in enumerate(self.torches):
            cx, cy = self._cell(c, r)
            flick = 0.8 + 0.2 * math.sin(t * 11 + k * 2.3) * math.sin(
                t * 7.3 + k)
            polish.glow(d, batch, cx, cy, s * 1.3 * flick, (255, 170, 70),
                        strength=55, group=card)
            d.append(pyglet.shapes.Rectangle(cx - s * 0.06, cy - s * 0.3,
                                             s * 0.12, s * 0.32,
                                             color=(90, 62, 40), batch=batch,
                                             group=body))
            d.append(pyglet.shapes.Triangle(
                cx - s * 0.13, cy, cx + s * 0.13, cy,
                cx + math.sin(t * 9 + k) * s * 0.05, cy + s * 0.34 * flick,
                color=(255, 190, 70), batch=batch, group=text))
        # The east gates glow for those who are through.
        for w, path in enumerate(temple.paths):
            cx, cy = self._cell(*path[-1])
            through = run.state[w] == model.ARRIVED
            polish.glow(d, batch, cx, cy, s * (1.15 if through else 0.8),
                        (255, 220, 120) if through else (200, 170, 110),
                        strength=90 if through else 40, group=card)
        # Devices.
        for i, dev in enumerate(temple.devices):
            cx, cy = self._cell(*temple.paths[dev.walker][dev.at])
            if dev.kind == model.BRIDGE:
                share = run.progress[i]
                moving = 0.0 < share < 1.0 or run.target[i] != (share >= 1)
                span = s * share
                if span > 0.5:
                    for j in range(4):
                        d.append(pyglet.shapes.Rectangle(
                            cx - s / 2, cy - s / 2 + j * s * 0.25 + 1, span,
                            s * 0.22, color=polish.mix(PLANK, (0, 0, 0),
                                                        0.1 * (j % 2)),
                            batch=batch, group=body))
                edge = (120, 255, 150) if share >= 1 else (
                    (255, 170, 60) if moving else (255, 80, 70))
                d.append(pyglet.shapes.Box(cx - s / 2, cy - s / 2, s, s,
                                           thickness=max(2.0, s * 0.08),
                                           color=edge, batch=batch,
                                           group=text))
            elif dev.kind == model.DOOR:
                share = run.progress[i]
                lift = s * 0.85 * share
                bars = 5
                for j in range(bars):
                    bx = cx - s * 0.4 + j * s * 0.2
                    d.append(pyglet.shapes.Rectangle(
                        bx - s * 0.035, cy - s / 2 + lift, s * 0.07,
                        s - lift if s - lift > 1 else 1,
                        color=(140, 146, 160), batch=batch, group=body))
                d.append(pyglet.shapes.Rectangle(
                    cx - s / 2, cy + s / 2 - s * 0.12, s, s * 0.12,
                    color=IRON, batch=batch, group=text))
                if share < 1:
                    d.append(pyglet.shapes.Rectangle(
                        cx - s * 0.45, cy - s / 2 + lift + s * 0.04,
                        s * 0.9, s * 0.08, color=(110, 116, 128),
                        batch=batch, group=body))
            else:
                on = run.jet_on(i)
                fire_in = run.jet_next(i)[0]
                if on:
                    h = s * (1.4 + 0.25 * math.sin(t * 23 + i))
                    polish.glow(d, batch, cx, cy, s * 1.1, (255, 120, 40),
                                strength=120, group=card)
                    for j, (wid, hue) in enumerate((
                            (0.45, (255, 90, 30)), (0.32, (255, 170, 40)),
                            (0.18, (255, 240, 150)))):
                        sway = math.sin(t * 17 + j * 2) * s * 0.06
                        d.append(pyglet.shapes.Triangle(
                            cx - s * wid, cy - s * 0.2, cx + s * wid,
                            cy - s * 0.2, cx + sway, cy - s * 0.2 + h * (
                                1 - j * 0.2), color=hue, batch=batch,
                            group=top))
                elif fire_in < model.WARN:
                    for j in range(5):
                        a = t * 9 + j * 1.3
                        rr = s * (0.15 + 0.25 * ((t * 3 + j * 0.2) % 1))
                        d.append(pyglet.shapes.Circle(
                            cx + math.cos(a) * rr, cy + math.sin(a) * rr,
                            max(1.5, s * 0.05), color=(255, 200, 80),
                            batch=batch, group=top))
                    d.append(pyglet.shapes.Circle(
                        cx, cy, s * 0.12, color=(255, 130, 50),
                        batch=batch, group=text))
                else:
                    d.append(pyglet.shapes.Circle(
                        cx, cy, s * 0.07, color=(90, 160, 255),
                        batch=batch, group=text))
            if dev.lever is not None:
                gx, gy = cx + s * 0.38, cy + s * 0.38
                hue = lever_colour(dev.lever)
                d.append(pyglet.shapes.Circle(gx, gy, s * 0.24,
                                              color=(30, 24, 26),
                                              batch=batch, group=text))
                d.append(pyglet.shapes.Circle(gx, gy, s * 0.19, color=hue,
                                              batch=batch, group=top))
                self._text(str(dev.lever + 1), gx, gy, max(7.0, s * 0.26),
                           bold=True, colour=(20, 16, 20, 255))
        # Walkers.
        for w in range(len(temple.paths)):
            hue = WALKER_COLOURS[w % len(WALKER_COLOURS)]
            for k, (c, r) in enumerate(self.trails[w]):
                px, py = self._cell(c, r)
                d.append(pyglet.shapes.Circle(
                    px, py - s * 0.2, s * 0.06, color=hue + (40 + 18 * k,),
                    batch=batch, group=body))
            state = run.state[w]
            if state in (model.FELL,):
                continue
            c, r = run.where(w)
            px, py = self._cell(c, r)
            bob = math.sin(t * 10 + w) * s * 0.04 if state == model.WALKING \
                else 0.0
            polish.glow(d, batch, px, py, s * 0.9, hue, strength=80,
                        group=card)
            d.append(pyglet.shapes.Ellipse(px, py - s * 0.32, s * 0.24,
                                           s * 0.08, color=(20, 14, 12, 120),
                                           batch=batch, group=body))
            body_c = (230, 80, 40) if state == model.BURNED else hue
            d.append(pyglet.shapes.RoundedRectangle(
                px - s * 0.22, py - s * 0.36 + bob, s * 0.44, s * 0.5,
                radius=s * 0.1, color=polish.darker(body_c, 0.15),
                batch=batch, group=top))
            d.append(pyglet.shapes.Circle(px, py + s * 0.26 + bob, s * 0.19,
                                          color=body_c, batch=batch,
                                          group=top))
            d.append(pyglet.shapes.Circle(px + s * 0.24, py - s * 0.02 + bob,
                                          s * 0.08, color=(255, 230, 120),
                                          batch=batch, group=top))
            if state == model.WAITING:
                for j in (-1, 1):
                    d.append(pyglet.shapes.Rectangle(
                        px + j * s * 0.08 - s * 0.03, py + s * 0.5,
                        s * 0.06, s * 0.2, color=(255, 255, 255),
                        batch=batch, group=top))
        # The lever panel.
        for k in range(len(temple.levers)):
            lx, ly, lw, lh = self._lever_box(k)
            hue = lever_colour(k)
            fresh = max(0.0, 1.0 - (t - run.pulled[k]) * 3) \
                if run.pulled[k] else 0.0
            polish.card(d, batch, lx, ly, lw, lh,
                        polish.mix((52, 44, 42), hue, 0.18 + 0.4 * fresh),
                        radius=10, edge=hue, group=card)
            mx, my = lx + lw * 0.3, ly + lh * 0.22
            d.append(pyglet.shapes.Rectangle(mx - lw * 0.16, my - lh * 0.05,
                                             lw * 0.32, lh * 0.1,
                                             color=(30, 26, 26), batch=batch,
                                             group=body))
            angle = math.radians(60 if self.flips[k] % 2 else 120)
            tip = (mx + math.cos(angle) * lh * 0.55,
                   my + math.sin(angle) * lh * 0.55)
            d.append(pyglet.shapes.Line(mx, my, tip[0], tip[1],
                                        thickness=max(3.0, lw * 0.06),
                                        color=(200, 200, 210), batch=batch,
                                        group=text))
            d.append(pyglet.shapes.Circle(tip[0], tip[1], lw * 0.08,
                                          color=hue, batch=batch, group=top))
            self._text(str(k + 1), lx + lw * 0.76, ly + lh * 0.58,
                       max(9.0, lh * 0.32), bold=True, colour=hue + (255,))
            # A gem for each device the lever works.
            count = len(temple.levers[k])
            for j in range(count):
                gx = lx + lw * 0.76 + (j - (count - 1) / 2) * lh * 0.2
                d.append(pyglet.shapes.Circle(gx, ly + lh * 0.2, lh * 0.07,
                                              color=hue, batch=batch,
                                              group=text))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        left = max(0, int(self.run.temple.seconds - self.run.t))
        return _('rung %d  %d/%d   %d s left') % (
            self.rung, self.trial, self.total_trials, left)
