# -*- coding: utf-8 -*-
"""Echo Cave on screen: down a cave behind a bat.

The view follows the bat down the cave. Rings of rock run away into
the dark, fading with distance and lit only as far as the light goes;
on the dark rungs a click lights them for a moment, and on the darkest
nothing does. Moths glow and flutter where they can be seen. Steer with
the mouse (the bat flies toward the pointer while it moves) or the
arrow keys / WASD; Space clicks.

For the agent boundary: ports 0-7 steer for one step (up, down, left,
right, then the four diagonals); port 8 clicks.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import echocave as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .pointer import Pointer
from .tones import Tones, patch

ROCK = (176, 136, 100)
BACK = 4.0                     # the eye trails the bat by this much
RINGS = 44
SPACING = 2.0
DIAGONALS = {(-1, 1): model.UP_LEFT, (1, 1): model.UP_RIGHT,
             (-1, -1): model.DOWN_LEFT, (1, -1): model.DOWN_RIGHT,
             (0, 1): model.UP, (0, -1): model.DOWN, (-1, 0): model.LEFT,
             (1, 0): model.RIGHT}


class EchoCave(Pointer, Tones, ClockedTask):
    """Through the cave, catching moths, without touching rock."""

    instance: Optional['EchoCave'] = None

    TITLE = 'Echo Cave'
    TASK_ID = 'echo_cave'
    PREFIX = 'ECHO'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    SUBSTEP = 1 / 120.0
    EVENT_KEYS = {key.SPACE: model.CLICK}
    FOOTNOTE = _('Mouse or arrows / WASD: steer   Space: click   Esc: menu')

    def __init__(self) -> None:
        self.last_pointer = None
        self.moved_at = -10.0
        self.view = None
        super().__init__()

    def _deal(self) -> bool:
        ok = super()._deal()
        level = self.run.level
        if level.see:
            self.message = _('Fly through; catch %d moths') % level.need
        elif level.flash:
            self.message = _('Dark: Space clicks and lights the cave')
        else:
            self.message = _('No light: fly by the echoes of your clicks')
        self.last_pointer = self.pointer
        self._tones_live(self.run.notes,
                         [patch(n, k + 1) for k, n in
                          enumerate(model.PATCHES)],
                         level.length / level.speed + 2.0)
        return ok

    def _held(self):
        k = self.keys
        x = (1 if k[key.RIGHT] or k[key.D] else 0) - \
            (1 if k[key.LEFT] or k[key.A] else 0)
        y = (1 if k[key.UP] or k[key.W] else 0) - \
            (1 if k[key.DOWN] or k[key.S] else 0)
        return DIAGONALS.get((x, y))

    def _tick(self) -> None:
        run = self.run
        if run is not None:
            if self.pointer != self.last_pointer:
                self.moved_at = run.t
                self.last_pointer = self.pointer
            if self.pointer and self.view and \
                    run.t - self.moved_at < 1.5 and self._held() is None:
                bx, by, focal = self.view
                k = BACK / focal
                run.aim = ((self.pointer[0] - bx) * k,
                           (self.pointer[1] - by) * k)
            else:
                run.aim = None
        super()._tick()

    # --- drawing --------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        d, batch = self.drawn, self.batch
        cave = run.cave
        level = run.level
        cx0, cy0 = left + width / 2, bottom + height / 2
        focal = min(width, height) * 0.9
        ez = run.z - BACK
        ax, ay = model.axis(cave, ez)
        ex, ey = 0.5 * (run.x + ax), 0.5 * (run.y + ay)

        def see(x, y, z):
            dz = z - ez
            if dz < 0.3:
                return None
            k = focal / dz
            return cx0 + (x - ex) * k, cy0 + (y - ey) * k, k

        polish.card(d, batch, left - 4, bottom - 4, width + 8, height + 8,
                    (6, 6, 10), radius=14, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        d.append(pyglet.shapes.Rectangle(left, bottom, width, height,
                                         color=(8, 8, 14), batch=batch,
                                         group=pyglet.graphics.Group(
                                             order=-14)))
        pad = 16

        def inside(x, y):
            return left + pad <= x <= left + width - pad and \
                bottom + pad <= y <= bottom + height - pad

        lit = run.lit()
        z0 = math.floor(run.z / SPACING) * SPACING
        for k in range(RINGS, -1, -1):
            z = z0 + k * SPACING
            ahead = z - run.z
            if ahead < -BACK + 0.6 or lit <= 0:
                continue
            fade = max(0.0, 1.0 - max(0.0, ahead) / lit)
            if fade <= 0.02:
                continue
            cx, cy = model.axis(cave, z)
            r = model.radius(cave, z)
            c = see(cx, cy, z)
            if c is None:
                continue
            g = pyglet.graphics.Group(order=-12 + (RINGS - k) // 4)
            pts = []
            for j in range(24):
                a = 2 * math.pi * j / 24
                wob = 1.0 + 0.06 * math.sin(a * 3 + z * 0.7)
                p = see(cx + r * wob * math.cos(a), cy + r * wob * math.sin(a),
                        z)
                pts.append(p[:2])
            colour = polish.mix((20, 16, 20), ROCK, fade) + (int(255 * fade),)
            thick = max(1.0, min(14.0, c[2] * 0.25))
            for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
                if not (inside(xa, ya) and inside(xb, yb)):
                    continue
                d.append(pyglet.shapes.Line(xa, ya, xb, yb, thickness=thick,
                                            color=colour, batch=batch,
                                            group=g))
        # Moths.
        for k in range(len(run.caught)):
            if run.caught[k]:
                continue
            mx, my, mz = run.moth(k)
            if not level.moths_seen or mz - run.z > lit or mz < ez + 0.5:
                continue
            p = see(mx, my, mz)
            if p is None or not inside(p[0], p[1]):
                continue
            s = max(1.5, 0.35 * p[2])
            flap = math.sin(run.t * 30 + k) * s
            g = pyglet.graphics.Group(order=20)
            polish.glow(d, batch, p[0], p[1], s * 3, (255, 240, 160),
                        strength=120, group=g)
            for side in (-1, 1):
                d.append(pyglet.shapes.Triangle(
                    p[0], p[1], p[0] + side * s * 1.6, p[1] + flap,
                    p[0] + side * s * 1.2, p[1] - s * 0.6,
                    color=(250, 236, 200), batch=batch, group=g))
        # The bat.
        b = see(run.x, run.y, run.z)
        if b is not None:
            self.view = (b[0], b[1], focal)
            s = 0.9 * b[2]
            flap = math.sin(run.t * 14) * s * 0.5
            g = pyglet.graphics.Group(order=40)
            if run.clicks and run.t - run.clicks[-1] < 0.12:
                polish.glow(d, batch, b[0], b[1], s * 2.2, (160, 200, 255),
                            strength=150, group=g)
            for side in (-1, 1):
                d.append(pyglet.shapes.Triangle(
                    b[0], b[1] + s * 0.2, b[0] + side * s * 1.8,
                    b[1] + flap + s * 0.3, b[0] + side * s * 1.1,
                    b[1] - s * 0.4, color=(60, 50, 70), batch=batch,
                    group=g))
                d.append(pyglet.shapes.Triangle(
                    b[0] + side * s * 1.8, b[1] + flap + s * 0.3,
                    b[0] + side * s * 1.1, b[1] - s * 0.4,
                    b[0] + side * s * 1.5, b[1] - s * 0.1 + flap * 0.5,
                    color=(90, 76, 100), batch=batch, group=g))
            d.append(pyglet.shapes.Circle(b[0], b[1], s * 0.45,
                                          color=(80, 66, 90), batch=batch,
                                          group=g))
            for side in (-1, 1):
                d.append(pyglet.shapes.Circle(b[0] + side * s * 0.16,
                                              b[1] + s * 0.12, s * 0.08,
                                              color=(255, 220, 120),
                                              batch=batch, group=g))
        # How far, and the moths caught.
        top = pyglet.graphics.Group(order=60)
        share = min(1.0, run.z / level.length)
        polish.rounded(d, batch, left + 20, bottom + 14, width - 40, 6,
                       (255, 255, 255, 40), radius=3, group=top)
        polish.rounded(d, batch, left + 20, bottom + 14,
                       max(6.0, (width - 40) * share), 6, (150, 190, 255),
                       radius=3, group=pyglet.graphics.Group(order=61))
        for k in range(len(run.caught)):
            x = left + 24 + k * 22
            y = bottom + height - 22
            got = run.caught[k]
            d.append(pyglet.shapes.Circle(
                x, y, 7, color=(255, 230, 140) if got else (255, 255, 255, 50),
                batch=batch, group=top))
        self._text(_('need %d') % level.need, left + 30 + len(run.caught) * 22,
                   bottom + height - 22, 10, anchor='left',
                   colour=(255, 255, 255, 160), group=top)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   moths %d of %d') % (
            self.rung, self.trial, self.total_trials, sum(run.caught),
            run.level.need)
