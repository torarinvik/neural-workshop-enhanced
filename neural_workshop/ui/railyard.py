# -*- coding: utf-8 -*-
"""Rail Yard on screen: a green valley, track on ballast, and trains.

Click a set of points to throw it (or press its number, 1-9); click a
tunnel's signal to turn it red or green (Q and W). Each train is
painted its station's colour and carries the station's letter. Points
show the way they lie in yellow, and orange with a filling ring while
they are moving -- a train that reaches them then comes off the rails.
Along the top, a chip for every train in the order they are due.

For the agent boundary: ports 0-14 throw the points numbered 1-15,
ports 15 and 16 work the two tunnel signals.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import railyard as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import polish
from .rungtask import RungTask

STATION_COLOURS = (
    (232, 84, 72), (246, 162, 44), (238, 206, 52), (124, 198, 82),
    (38, 168, 122), (44, 186, 204), (62, 130, 232), (124, 100, 222),
    (190, 92, 212), (232, 92, 162), (164, 112, 64), (118, 128, 140),
    (252, 136, 112), (182, 222, 104), (104, 202, 242), (172, 142, 244))
LETTERS = 'ABCDEFGHIJKLMNOP'
BALLAST = (172, 162, 146)
SLEEPER = (112, 84, 58)
RAIL = (214, 218, 228)
POINTS_SET = (255, 214, 64)
POINTS_MOVING = (255, 128, 40)
SIGNAL_GO = (60, 220, 110)
SIGNAL_STOP = (236, 64, 56)


def station_colour(i: int) -> Tuple[int, int, int]:
    return STATION_COLOURS[i % len(STATION_COLOURS)]


class RailYard(RungTask):
    """Get every train to its own station."""

    instance: Optional['RailYard'] = None

    TITLE = 'Rail Yard'
    TASK_ID = 'rail_yard'
    PREFIX = 'RAILYARD'
    CATEGORY = 'planning'
    FEEDBACK = 3.0
    FOOTNOTE = _('click points to throw them (1-9)   click a signal '
                 '(Q, W)   Esc: menu')

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        self.last_tick = 0.0
        self.scenery: List[object] = []
        self.scenery_key = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.run = None
        self._drop_scenery()

    def _drop_scenery(self) -> None:
        for item in self.scenery:
            try:
                item.delete()
            except Exception:
                pass
        self.scenery = []
        self.scenery_key = None

    def close(self) -> None:
        if type(self).instance is self:
            self._drop_scenery()
        super().close()

    def _deal(self) -> bool:
        self.run = model.Run(model.deal(self.rung, rng=self.rng))
        self.last_tick = self.clock()
        self.message = _('Every train to the station of its colour')
        self._drop_scenery()
        return True

    # --- controls --------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY or self.run is None:
            return
        if 0 <= port < model.SIGNAL_PORT:
            self.run.throw(port)
        elif model.SIGNAL_PORT <= port < model.PORTS:
            self.run.signal(port - model.SIGNAL_PORT)

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._9:
            self.steer(symbol - key._1)
        elif symbol == key.Q:
            self.steer(model.SIGNAL_PORT)
        elif symbol == key.W:
            self.steer(model.SIGNAL_PORT + 1)

    def _click(self, x: float, y: float, button: int) -> None:
        if self.run is None:
            return
        lay = self.run.yard.layout
        scale = self._frame()[2]
        best, port = (4.5 * scale) ** 2, None
        for k, n in enumerate(lay.switch_nodes):
            px, py = self._at(lay.nodes[n].x, lay.nodes[n].y)
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best:
                best, port = d, k
        for j in range(len(self.run.signals)):
            px, py = self._signal_at(j)
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best:
                best, port = d, model.SIGNAL_PORT + j
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

    # --- geometry --------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        head = height * 0.08
        scale = min(width / model.WORLD_W, (height - head) / model.WORLD_H)
        x0 = left + (width - model.WORLD_W * scale) / 2
        return x0, bottom, scale

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    def _signal_at(self, j: int) -> Tuple[float, float]:
        lay = self.run.yard.layout
        portal = [n for n in lay.nodes if n.kind == 'portal'][j]
        return self._at(portal.x + 3.0, portal.y + 6.5)

    # --- scenery, drawn once a yard ---------------------------------------

    def _build_scenery(self) -> None:
        self._drop_scenery()
        run = self.run
        lay = run.yard.layout
        x0, y0, s = self._frame()
        W, H = model.WORLD_W * s, model.WORLD_H * s
        out = self.scenery
        batch = self.batch
        dark = self.dark
        low, high = ((52, 84, 50), (72, 110, 64)) if dark else \
            ((104, 156, 84), (142, 192, 110))
        pal = polish.palette(dark)
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12,
                    polish.darker(low, 0.25), radius=18, shade=pal.shadow,
                    group=polish.STAGE)
        polish.gradient(out, batch, x0, y0, W, H, low, high, bands=20,
                        group=polish.CARD)
        # Trees, stones and flowers, kept off the track.
        draw = random.Random(len(lay.nodes) * 131 + run.yard.level.depth)
        pts = []
        for seg in lay.segments:
            d = 0.0
            while d <= seg.length:
                pts.append(model.position(lay, lay.segments.index(seg), d)[:2])
                d += 3.0
        for n in lay.nodes:
            pts.append((n.x, n.y))
            if n.kind == 'station':
                pts += [(n.x + 4, n.y), (n.x + 8, n.y)]

        def clear(x, y, r):
            return all((x - px) ** 2 + (y - py) ** 2 > r * r
                       for px, py in pts)
        tree_g = pyglet.graphics.Group(order=-12)
        top_g = pyglet.graphics.Group(order=-11)
        for _k in range(260):
            x = draw.uniform(2, model.WORLD_W - 2)
            y = draw.uniform(2, model.WORLD_H - 2)
            kind = draw.random()
            if kind < 0.45 and clear(x, y, 6.0):
                r = draw.uniform(1.8, 3.2)
                px, py = self._at(x, y)
                shade = draw.uniform(0.0, 0.25)
                leaf = polish.mix((46, 112, 58), (24, 70, 40), shade)
                out.append(pyglet.shapes.Circle(
                    px + r * s * 0.25, py - r * s * 0.3, r * s,
                    color=(20, 40, 20, 70), batch=batch, group=tree_g))
                out.append(pyglet.shapes.Circle(
                    px, py, r * s, color=leaf, batch=batch, group=tree_g))
                out.append(pyglet.shapes.Circle(
                    px - r * s * 0.3, py + r * s * 0.3, r * s * 0.45,
                    color=polish.lighter(leaf, 0.2), batch=batch,
                    group=top_g))
            elif kind < 0.6 and clear(x, y, 3.0):
                px, py = self._at(x, y)
                out.append(pyglet.shapes.Ellipse(
                    px, py, s * draw.uniform(0.8, 1.4), s * 0.7,
                    color=(150, 150, 140), batch=batch, group=tree_g))
            elif kind < 0.85 and clear(x, y, 2.5):
                px, py = self._at(x, y)
                petal = draw.choice(((250, 240, 120), (250, 250, 250),
                                     (240, 160, 200), (180, 200, 255)))
                out.append(pyglet.shapes.Circle(
                    px, py, max(1.2, s * 0.35), color=petal, batch=batch,
                    group=tree_g))
        # Track: ballast, sleepers, rails.
        ballast_g = pyglet.graphics.Group(order=-10)
        sleeper_g = pyglet.graphics.Group(order=-9)
        rail_g = pyglet.graphics.Group(order=-8)
        for index, seg in enumerate(lay.segments):
            sp = [self._at(*p) for p in seg.points]
            for (ax, ay), (bx, by) in zip(sp, sp[1:]):
                out.append(pyglet.shapes.Line(
                    ax, ay, bx, by, thickness=3.6 * s, color=BALLAST,
                    batch=batch, group=ballast_g))
                out.append(pyglet.shapes.Circle(
                    bx, by, 1.8 * s, color=BALLAST, batch=batch,
                    group=ballast_g))
            d = 1.0
            while d < seg.length:
                x, y, h = model.position(lay, index, d)
                nx, ny = -math.sin(h) * 1.7, math.cos(h) * 1.7
                a, b = self._at(x - nx, y - ny), self._at(x + nx, y + ny)
                out.append(pyglet.shapes.Line(
                    a[0], a[1], b[0], b[1], thickness=max(1.0, 0.75 * s),
                    color=SLEEPER, batch=batch, group=sleeper_g))
                d += 2.4
            for side in (-0.8, 0.8):
                for p, q in zip(seg.points, seg.points[1:]):
                    h = math.atan2(q[1] - p[1], q[0] - p[0])
                    nx, ny = -math.sin(h) * side, math.cos(h) * side
                    a = self._at(p[0] + nx, p[1] + ny)
                    b = self._at(q[0] + nx, q[1] + ny)
                    out.append(pyglet.shapes.Line(
                        a[0], a[1], b[0], b[1],
                        thickness=max(1.0, 0.38 * s), color=RAIL,
                        batch=batch, group=rail_g))
        # Stations.
        build_g = pyglet.graphics.Group(order=-7)
        roof_g = pyglet.graphics.Group(order=-6)
        size = calc_fontsize(11)
        for n in lay.nodes:
            if n.kind == 'station':
                colour = station_colour(n.index)
                bx, by = self._at(n.x + 1.0, n.y - 2.6)
                polish.card(out, batch, bx, by, 9.0 * s, 5.2 * s,
                            (236, 230, 216), radius=s * 0.8,
                            shade=(20, 40, 20, 60), lift=2, group=build_g)
                rx, ry = self._at(n.x + 0.4, n.y + 1.6)
                out.append(pyglet.shapes.RoundedRectangle(
                    rx, ry, 10.2 * s, 1.8 * s, s * 0.5, color=colour,
                    batch=batch, group=roof_g))
                lx, ly = self._at(n.x + 5.5, n.y - 0.6)
                out.append(pyglet.text.Label(
                    LETTERS[n.index], font_size=max(7.0, s * 2.4),
                    weight='bold', color=polish.darker(colour, 0.35) + (255,),
                    x=lx, y=ly, anchor_x='center', anchor_y='center',
                    batch=batch, group=self.text_group))
            elif n.kind == 'portal':
                px, py = self._at(n.x - 1.0, n.y)
                out.append(pyglet.shapes.Sector(
                    px, py, 5.2 * s, angle=180.0, start_angle=-90.0,
                    color=(120, 112, 104), batch=batch, group=build_g))
                out.append(pyglet.shapes.Sector(
                    px, py, 3.6 * s, angle=180.0, start_angle=-90.0,
                    color=(22, 22, 28), batch=batch, group=roof_g))
            elif n.kind == 'switch':
                lx, ly = self._at(n.x - 2.2, n.y + 4.4)
                if n.index < 9:
                    out.append(pyglet.text.Label(
                        str(n.index + 1), font_size=max(7.0, s * 1.9),
                        weight='bold', color=(255, 255, 255, 230),
                        x=lx, y=ly, anchor_x='center', anchor_y='center',
                        batch=batch, group=self.text_group))
        _ = size
        self.scenery_key = (id(self.batch), id(run.yard), self._frame())

    # --- each frame ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if self.scenery_key != (id(self.batch), id(run.yard), self._frame()):
            self._build_scenery()
        lay = run.yard.layout
        x0, y0, s = self._frame()
        batch = self.batch
        pal = polish.palette(self.dark)
        # Points.
        for k, n in enumerate(lay.switch_nodes):
            node = lay.nodes[n]
            p = run.points[k]
            px, py = self._at(node.x, node.y)
            moving = p.moving > 0
            colour = POINTS_MOVING if moving else POINTS_SET
            seg = lay.segments[lay.out[n][p.target]]
            reach = min(7.0, seg.length * 0.5)
            pts = []
            d = 0.0
            while d <= reach:
                pts.append(self._at(*model.position(
                    lay, lay.out[n][p.target], d)[:2]))
                d += 1.0
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                self.drawn.append(pyglet.shapes.Line(
                    ax, ay, bx, by, thickness=1.3 * s, color=colour,
                    batch=batch, group=self.card_group))
            self.drawn.append(pyglet.shapes.Circle(
                px, py, 2.2 * s, color=(40, 44, 56), batch=batch,
                group=self.body_group))
            self.drawn.append(pyglet.shapes.Circle(
                px, py, 1.5 * s, color=colour, batch=batch,
                group=self.text_group))
            if moving and run.yard.level.throw > 0:
                share = 1.0 - p.moving / run.yard.level.throw
                self.drawn.append(pyglet.shapes.Arc(
                    px, py, 3.0 * s, thickness=max(2.0, 0.6 * s),
                    angle=-360.0 * share, start_angle=90.0, color=colour,
                    batch=batch, group=self.top_group))
        # Signals and the queues behind them.
        portals = [nd for nd in lay.nodes if nd.kind == 'portal']
        for j, nd in enumerate(portals):
            sx, sy = self._signal_at(j)
            bx, by = self._at(nd.x + 3.0, nd.y + 2.0)
            self.drawn.append(pyglet.shapes.Line(
                bx, by, sx, sy, thickness=max(1.5, 0.5 * s),
                color=(60, 62, 70), batch=batch, group=self.body_group))
            go = run.signals[j]
            lamp = SIGNAL_GO if go else SIGNAL_STOP
            polish.glow(self.drawn, batch, sx, sy, 3.6 * s, lamp,
                        strength=150, group=self.body_group)
            self.drawn.append(pyglet.shapes.Circle(
                sx, sy, 1.9 * s, color=(30, 30, 36), batch=batch,
                group=self.text_group))
            self.drawn.append(pyglet.shapes.Circle(
                sx, sy, 1.4 * s, color=lamp, batch=batch,
                group=self.top_group))
            queue = [o for o in run.trains if o.state == 'waiting'
                     and o.plan.portal == j]
            qx, qy = self._at(nd.x - 2.5, nd.y - 6.0)
            for i, o in enumerate(sorted(queue, key=lambda o: o.plan.due)):
                self.drawn.append(pyglet.shapes.Circle(
                    qx + i * 2.4 * s, qy, 1.0 * s,
                    color=station_colour(o.plan.station), batch=batch,
                    group=self.top_group))
        # Trains.
        for o in run.trains:
            if o.state == 'running' or (o.state == 'lost'
                                        and o.segment >= 0):
                self._train(o, s)
        if run.crash is not None:
            cx, cy = self._at(*run.crash)
            self.drawn.append(pyglet.shapes.Star(
                cx, cy, 6.0 * s, 2.6 * s, 10, color=(255, 170, 40),
                batch=batch, group=self.top_group))
            self.drawn.append(pyglet.shapes.Star(
                cx, cy, 3.6 * s, 1.4 * s, 8, color=(255, 240, 160),
                batch=batch, group=pyglet.graphics.Group(order=6)))
        # A chip for every train, along the top.
        n = len(run.trains)
        chip = min(width * 0.8 / max(n, 1), height * 0.05)
        cx0 = left + width / 2 - chip * (n - 1) / 2
        cy = bottom + height - chip * 0.7
        for i, o in enumerate(run.trains):
            colour = station_colour(o.plan.station)
            x = cx0 + i * chip
            if o.state in ('due', 'waiting'):
                self.drawn.append(pyglet.shapes.Arc(
                    x, cy, chip * 0.32, thickness=2, color=colour,
                    batch=batch, group=self.body_group))
            else:
                face = colour if o.state in ('running', 'right') else \
                    pal.muted
                self.drawn.append(pyglet.shapes.Circle(
                    x, cy, chip * 0.34, color=face, batch=batch,
                    group=self.body_group))
                if o.state == 'right':
                    self._text('✓', x, cy, chip * 0.32, bold=True,
                               colour=(255, 255, 255, 255))
                elif o.state in ('wrong', 'lost'):
                    self._text('×', x, cy, chip * 0.36, bold=True,
                               colour=(255, 255, 255, 255))

    def _train(self, o: model.Train, s: float) -> None:
        lay = self.run.yard.layout
        x, y, h = model.position(lay, o.segment, o.distance)
        colour = station_colour(o.plan.station)
        length = model.LENGTH * (1.75 if o.plan.express else 1.3)
        half_w = 1.75
        ca, sa = math.cos(h), math.sin(h)

        def at(dx, dy):
            return self._at(x + dx * ca - dy * sa, y + dx * sa + dy * ca)
        # Smoke, trailing.
        if o.state == 'running':
            for k in range(4):
                back = length + 1.0 + k * 1.6
                wob = math.sin(self.run.t * 6 + k + o.number) * 0.5
                px, py = at(-back + length * 0.75, 2.0 + k * 0.9 + wob)
                self.drawn.append(pyglet.shapes.Circle(
                    px, py, (0.9 + k * 0.45) * s,
                    color=(235, 235, 240, max(20, 150 - k * 38)),
                    batch=self.batch, group=self.body_group))
        shadow = [at(-length + 0.5, -half_w - 0.6), at(0.5, -half_w - 0.6),
                  at(0.5, half_w - 0.6), at(-length + 0.5, half_w - 0.6)]
        self.drawn.append(pyglet.shapes.Polygon(
            *shadow, color=(20, 30, 20, 80), batch=self.batch,
            group=self.card_group))
        body = [at(-length, -half_w), at(0, -half_w), at(0.9, 0),
                at(0, half_w), at(-length, half_w)]
        self.drawn.append(pyglet.shapes.Polygon(
            *body, color=polish.darker(colour, 0.3), batch=self.batch,
            group=self.body_group))
        inner = [at(-length + 0.35, -half_w + 0.35), at(-0.2, -half_w + 0.35),
                 at(0.5, 0), at(-0.2, half_w - 0.35),
                 at(-length + 0.35, half_w - 0.35)]
        self.drawn.append(pyglet.shapes.Polygon(
            *inner, color=colour, batch=self.batch, group=self.text_group))
        if o.plan.express:
            stripe = [at(-length + 0.4, -0.25), at(-0.3, -0.25),
                      at(-0.3, 0.25), at(-length + 0.4, 0.25)]
            self.drawn.append(pyglet.shapes.Polygon(
                *stripe, color=(255, 255, 255), batch=self.batch,
                group=self.top_group))
        win = [at(-2.0, -1.0), at(-0.7, -1.0), at(-0.7, 1.0), at(-2.0, 1.0)]
        self.drawn.append(pyglet.shapes.Polygon(
            *win, color=(230, 244, 255), batch=self.batch,
            group=self.top_group))
        lx, ly = at(-length * 0.55, 0)
        self._text(LETTERS[o.plan.station], lx, ly, max(7.0, s * 1.8),
                   bold=True, colour=(255, 255, 255, 255),
                   group=pyglet.graphics.Group(order=6))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   home %d of %d   %d s left') % (
            self.rung, self.trial, self.total_trials, run.right_count(),
            len(run.trains), max(0, int(run.yard.seconds - run.t)))
