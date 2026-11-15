# -*- coding: utf-8 -*-
"""Crane on screen: a harbour at dawn, a gantry, and swinging boxes.

Hold Left and Right to drive the trolley, Up and Down to work the
hoist; Space grabs a container under the hook or sets the carried one
down. Containers wear their bay's colour; bays are painted on the quay
with the same colour. A windsock and drifting streaks show the wind.

For the agent boundary: ports 0 and 1 drive the trolley left and
right for one step, 2 and 3 hoist up and down, 4 grabs or releases.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Optional, Tuple

import pyglet
from pyglet.window import key

from .. import crane as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask

BOX_COLOURS = ((222, 72, 60), (52, 120, 214), (60, 168, 96),
               (240, 150, 40), (150, 92, 196))
STEEL = (238, 176, 42)
STEEL_DARK = (176, 120, 24)
SEA_TOP = (70, 150, 196)
SEA_DEEP = (30, 84, 140)
QUAY = (168, 164, 158)
HULL = (54, 62, 80)
INK = (250, 250, 252, 255)


def box_colour(c: int) -> Tuple[int, int, int]:
    return BOX_COLOURS[c % len(BOX_COLOURS)]


class Crane(ClockedTask):
    """Every container to its own bay, with nothing knocked."""

    instance: Optional['Crane'] = None

    TITLE = 'Crane'
    TASK_ID = 'crane'
    PREFIX = 'CRANE'
    CATEGORY = 'planning'
    FEEDBACK = 3.0
    MODEL = model
    FOOTNOTE = _('Left / Right: trolley   Up / Down: hoist   '
                 'Space: grab or release   Esc: menu')
    EVENT_KEYS = {key.SPACE: model.GRAB, key.ENTER: model.GRAB,
                  key.RETURN: model.GRAB}

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Each container to the bay of its colour')
        return ok

    def _held(self) -> Optional[int]:
        k = self.keys
        if k[key.LEFT] or k[key.A]:
            return model.LEFT
        if k[key.RIGHT] or k[key.D]:
            return model.RIGHT
        if k[key.UP] or k[key.W]:
            return model.UP
        if k[key.DOWN] or k[key.S]:
            return model.DOWN
        return None

    # --- geometry ---------------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        s = min(width / model.WORLD_W, height / (model.WORLD_H + 2.4))
        x0 = left + (width - model.WORLD_W * s) / 2
        return x0, bottom + 0.9 * s, s

    def _at(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    # --- the harbour, built once ----------------------------------------------------

    def _build_scenery(self) -> None:
        run = self.run
        yard = run.yard
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        pal = polish.palette(self.dark)
        W, H = model.WORLD_W * s, model.WORLD_H * s
        polish.card(out, batch, x0 - 6, y0 - 0.9 * s - 6, W + 12,
                    H + 0.9 * s + 12, (40, 50, 70), radius=14,
                    shade=pal.shadow, group=polish.STAGE)
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        polish.gradient(out, batch, x0, y0, W, H, (250, 196, 150),
                        (110, 140, 200), bands=24, group=g0)
        sun = self._at(30.0, 13.0)
        polish.glow(out, batch, sun[0], sun[1], 5.5 * s, (255, 226, 160),
                    strength=120, group=g0)
        out.append(pyglet.shapes.Circle(sun[0], sun[1], 1.8 * s,
                                        color=(255, 236, 190), batch=batch,
                                        group=g0))
        # Far hills and the city.
        draw = random.Random(yard.gust_seed)
        for k in range(14):
            bx = 18.0 + k * 1.9 + draw.uniform(-0.3, 0.3)
            bh = draw.uniform(2.0, 6.5)
            px, py = self._at(bx, 0.0)
            out.append(pyglet.shapes.Rectangle(
                px, py, 1.5 * s, (bh + 1.5) * s, color=(150, 140, 168),
                batch=batch, group=g0))
        # The sea, left; the quay, right.
        sx, sy = self._at(0, -0.9)
        polish.gradient(out, batch, sx, sy, 17.0 * s, 3.3 * s, SEA_DEEP,
                        SEA_TOP, bands=6, group=g1)
        qx, qy = self._at(17.0, 0)
        out.append(pyglet.shapes.Rectangle(qx, qy - 0.9 * s, W - 17.0 * s,
                                           0.9 * s, color=QUAY, batch=batch,
                                           group=g1))
        # Bays: painted outlines on the quay.
        for bay in yard.bays:
            hue = box_colour(bay.colour)
            bx, by = self._at(bay.x - model.BOX_W / 2 - 0.2, -0.55)
            out.append(pyglet.shapes.Rectangle(
                bx, by, (model.BOX_W + 0.4) * s, 0.5 * s, color=hue,
                batch=batch, group=g1))
            for side in (-1, 1):
                lx, ly = self._at(bay.x + side * (model.BOX_W / 2 + 0.2), 0)
                out.append(pyglet.shapes.Line(lx, ly, lx, ly + 1.2 * s,
                                              thickness=2,
                                              color=hue + (160,),
                                              batch=batch, group=g1))
        # The wall of stacked boxes in the middle.
        if run.level.wall:
            n = int(round(run.level.wall / model.BOX_H))
            for k in range(n):
                bx, by = self._at(yard.wall_x - 1.6, k * model.BOX_H)
                tone = (120 + 12 * (k % 2), 126, 136)
                out.append(pyglet.shapes.Rectangle(
                    bx, by, 3.2 * s, model.BOX_H * s - 1, color=tone,
                    batch=batch, group=g1))
                for j in range(1, 7):
                    out.append(pyglet.shapes.Line(
                        bx + j * 3.2 * s / 7, by + 2, bx + j * 3.2 * s / 7,
                        by + model.BOX_H * s - 3, thickness=1,
                        color=polish.darker(tone, 0.15), batch=batch,
                        group=g1))
        # The gantry: legs and the rail girder.
        for lx_w in (0.6, model.WORLD_W - 0.6):
            lx, ly = self._at(lx_w, -0.9)
            out.append(pyglet.shapes.Rectangle(lx - 0.35 * s, ly, 0.7 * s,
                                               (model.RAIL + 1.5) * s,
                                               color=STEEL_DARK, batch=batch,
                                               group=g1))
        gx, gy = self._at(0.2, model.RAIL + 0.15)
        out.append(pyglet.shapes.Rectangle(gx, gy, (model.WORLD_W - 0.4) * s,
                                           0.8 * s, color=STEEL, batch=batch,
                                           group=g1))
        for k in range(22):
            ax, ay = self._at(0.2 + k * 2.0, model.RAIL + 0.15)
            out.append(pyglet.shapes.Line(ax, ay, ax + 2.0 * s, ay + 0.8 * s,
                                          thickness=2, color=STEEL_DARK,
                                          batch=batch, group=g1))

    # --- each frame -------------------------------------------------------------------

    def _box(self, d, cx: float, bottom: float, colour: int, glow=False,
             group=None) -> None:
        """A container centred on world x *cx*, resting at *bottom*."""
        s = self._frame()[2]
        batch = self.batch
        hue = box_colour(colour)
        px, py = self._at(cx - model.BOX_W / 2, bottom)
        w, h = model.BOX_W * s, model.BOX_H * s
        if glow:
            polish.glow(d, batch, px + w / 2, py + h / 2, w * 0.8, hue,
                        strength=80, group=self.card_group)
        d.append(pyglet.shapes.Rectangle(px, py, w, h, color=hue,
                                         batch=batch, group=group or
                                         self.body_group))
        for j in range(1, 8):
            d.append(pyglet.shapes.Line(px + j * w / 8, py + 2, px + j * w / 8,
                                        py + h - 2, thickness=1,
                                        color=polish.darker(hue, 0.2),
                                        batch=batch, group=self.text_group))
        d.append(pyglet.shapes.Box(px, py, w, h, thickness=2,
                                   color=polish.darker(hue, 0.35),
                                   batch=batch, group=self.text_group))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        yard = run.yard
        self._scenery_fresh(self._frame())
        x0, y0, s = self._frame()
        d, batch = self.drawn, self.batch
        t = run.t
        # The ship, rolling.
        roll = run.roll()
        hx0, hy0 = self._at(model.SHIP_X[0] - 0.8, model.DECK + roll - 2.4)
        d.append(pyglet.shapes.Polygon(
            (hx0, hy0 + 2.4 * s), (hx0 + 14.6 * s, hy0 + 2.4 * s),
            (hx0 + 13.2 * s, hy0), (hx0 + 1.2 * s, hy0),
            color=HULL, batch=batch, group=self.card_group))
        d.append(pyglet.shapes.Rectangle(hx0, hy0 + 2.2 * s, 14.6 * s,
                                         0.25 * s, color=(214, 70, 60),
                                         batch=batch, group=self.body_group))
        # Waves.
        for k in range(9):
            wx = (k * 2.1 + t * 0.6) % 17.0
            px, py = self._at(wx, 1.8 + 0.25 * math.sin(t * 1.3 + k))
            d.append(pyglet.shapes.Arc(px, py, 0.5 * s, angle=180,
                                       start_angle=0, thickness=2,
                                       color=(210, 236, 250, 160),
                                       batch=batch, group=self.body_group))
        # Containers.
        for i, box in enumerate(yard.boxes):
            if run.where[i][0] == 'held':
                continue
            cx, by = run.box_rect(i)
            self._box(d, cx, by, box.colour, glow=run.where[i][0] == 'bay')
        # Trolley, cable, hook and load.
        tx, ty = self._at(run.x, model.RAIL)
        hx, hy = run.hook()
        px, py = self._at(hx, hy)
        d.append(pyglet.shapes.Line(tx, ty, px, py, thickness=2,
                                    color=(50, 50, 60), batch=batch,
                                    group=self.body_group))
        d.append(pyglet.shapes.RoundedRectangle(
            tx - 1.0 * s, ty - 0.2 * s, 2.0 * s, 0.9 * s, radius=0.15 * s,
            color=(60, 66, 84), batch=batch, group=self.text_group))
        for side in (-0.6, 0.6):
            d.append(pyglet.shapes.Circle(tx + side * s, ty + 0.75 * s,
                                          0.22 * s, color=(30, 30, 40),
                                          batch=batch, group=self.top_group))
        held = run.held
        ready = held is None and run.grabbable() is not None
        d.append(pyglet.shapes.Rectangle(
            px - 0.45 * s, py, 0.9 * s, 0.35 * s,
            color=(255, 220, 80) if ready else (240, 200, 60),
            batch=batch, group=self.top_group))
        if ready:
            polish.glow(d, batch, px, py, 1.2 * s, (255, 240, 120),
                        strength=120, group=self.card_group)
        if held is not None:
            self._box(d, hx, hy - model.BOX_H, yard.boxes[held].colour,
                      group=self.text_group)
            # Where it would land, dropped now.
            below = run.surface(hx)
            gx, gy = self._at(hx - model.BOX_W / 2, below)
            d.append(pyglet.shapes.Box(gx, gy, model.BOX_W * s, 3,
                                       thickness=2,
                                       color=(255, 255, 255, 150),
                                       batch=batch, group=self.top_group))
        # Wind: a sock on the gantry and streaks drifting.
        push = run.push()
        sx, sy = self._at(model.WORLD_W - 0.6, model.RAIL + 1.2)
        lean = max(-1.0, min(1.0, push / 1.2))
        for k in range(4):
            d.append(pyglet.shapes.Rectangle(
                sx + lean * k * 0.45 * s - 0.2 * s,
                sy - (1 - abs(lean)) * k * 0.3 * s,
                0.45 * s, 0.3 * s,
                color=(240, 90, 60) if k % 2 == 0 else (250, 250, 250),
                batch=batch, group=self.top_group))
        if abs(push) > 0.05:
            for k in range(10):
                phase = (t * 0.35 * math.copysign(1, push) + k * 0.1) % 1.0
                wx = phase * model.WORLD_W
                wy = 4.0 + (k * 7.3) % 16.0
                ax, ay = self._at(wx, wy)
                d.append(pyglet.shapes.Line(
                    ax, ay, ax - math.copysign(1.4 * s * min(1.5,
                                                             abs(push)), push),
                    ay, thickness=1, color=(255, 255, 255, 110),
                    batch=batch, group=self.top_group))
        # Along the top: one chip a container, filled once in its bay.
        top = y0 + (model.WORLD_H + 0.3) * s
        for i, box in enumerate(yard.boxes):
            cx = x0 + (1.0 + i * 1.4) * s
            done = run.where[i][0] == 'bay'
            d.append(pyglet.shapes.Rectangle(
                cx, top, 1.1 * s, 0.7 * s,
                color=box_colour(box.colour) if done else (200, 204, 214),
                batch=batch, group=self.body_group))
        share = max(0.0, 1.0 - t / run.level.seconds)
        bw = 14.0 * s
        bx = x0 + model.WORLD_W * s - bw - 0.5 * s
        polish.rounded(d, batch, bx, top, bw, 0.7 * s, (190, 196, 208),
                       radius=0.35 * s, group=self.card_group)
        if share > 0.02:
            polish.rounded(d, batch, bx, top, bw * share, 0.7 * s,
                           polish.mix((236, 80, 64), (60, 190, 120),
                                      min(1.0, share * 1.6)),
                           radius=0.35 * s, group=self.body_group)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   %d of %d placed') % (
            self.rung, self.trial, self.total_trials, self.run.placed,
            len(self.run.yard.boxes))
