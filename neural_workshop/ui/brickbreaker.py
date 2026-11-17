# -*- coding: utf-8 -*-
"""3D Brick Breaker on screen: the box seen from just behind the paddle.

The mouse slides the paddle across the opening; the arrow keys tilt it
(Left and Right turn its face that way, Up and Down tip it); Enter
levels it and Space changes its colour, where colour matters. W A S D
slide it too. The paddle is drawn as a frame, to be seen through, with
a rod standing out of its middle that shows which way it faces. The
light is overhead, so the ball's shadow on the floor tells how far
back it is.

Bricks: pale ones break for any ball; red, green and blue ones only
for a ball of their colour; a raised plate means another hit is
needed; grey metal never breaks; black with a red stud is a mine;
orange with a black stud is a bomb. A numbered brick breaks only when
its number is the lowest left, and that one is lit.

For the agent boundary: ports 0-7 slide the paddle left, right, up,
down and the diagonals; 8-11 turn its face left, right, up and down;
12 levels it; 13 changes its colour.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pyglet
from pyglet.math import Mat4, Vec3, Vec4
from pyglet.window import key

from .. import brickbreaker as model
from .. import display, state
from ..geometry import (calc_fontsize, framebuffer_size, from_bottom_edge,
                        from_top_edge, pixel_size)
from ..i18n import _
from . import render3d
from .clocked import ClockedTask
from .tones import Tones
from .verdict import above_the_band

W, H, D = model.WIDE, model.HIGH, model.DEEP
LIGHT = render3d.Light(direction=(0.08, 0.72, 0.68),
                       colour=(1.0, 0.98, 0.94), sky=(0.80, 0.82, 0.88),
                       ground=(0.62, 0.62, 0.66), span=3.6)
WALL, FLOOR, BACK = (0.78, 0.81, 0.90), (0.50, 0.55, 0.68), (0.34, 0.38, 0.50)
RIB = (0.30, 0.33, 0.44)
INKS = ((0.90, 0.88, 0.82), (0.88, 0.27, 0.25), (0.25, 0.70, 0.36),
        (0.27, 0.48, 0.92))
NAMES = ('', _('red'), _('green'), _('blue'))
STEEL, MINE, BOMB = (0.62, 0.65, 0.70), (0.09, 0.09, 0.11), (0.95, 0.55, 0.12)
LIT = (1.0, 0.93, 0.45)
IDENTITY = Mat4()


def _ball(builder: render3d.Builder, rings: int = 16,
          segments: int = 24) -> None:
    """A unit sphere, wound anticlockwise seen from outside."""
    base = len(builder.positions) // 3
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        y, r = math.cos(phi), math.sin(phi)
        for step in range(segments + 1):
            theta = 2.0 * math.pi * step / segments
            p = (r * math.cos(theta), y, r * math.sin(theta))
            builder.positions.extend(p)
            builder.normals.extend(p)
    for ring in range(rings):
        for step in range(segments):
            a = base + ring * (segments + 1) + step
            b = a + segments + 1
            builder.indices.extend((a, a + 1, b + 1, a, b + 1, b))


class BrickBreaker(Tones, ClockedTask):
    """Keep the ball in play; break the wall."""

    instance: Optional['BrickBreaker'] = None

    TITLE = '3D Brick Breaker'
    TASK_ID = 'brick_breaker_3d'
    PREFIX = 'BRICKS3D'
    CATEGORY = 'attention'
    MODEL = model
    SUBSTEP = 1 / 120.0
    FEEDBACK = 1.6
    EVENT_KEYS = {key.SPACE: model.COLOUR, key.RETURN: model.LEVEL,
                  key.ENTER: model.LEVEL}
    FOOTNOTE = _('mouse: slide the paddle   arrows: tilt it   Enter: level '
                 '  Space: colour   Esc: menu')

    def __init__(self) -> None:
        self.stage = render3d.Stage()
        self.meshes = {}
        self.view_proj: Optional[Mat4] = None
        self.rect = (0.0, 0.0, 1.0, 1.0)
        super().__init__()
        if self.stage.ok:
            for name, make in (('box', lambda b: b.box(-1.0, -1.0, -1.0,
                                                       1.0, 1.0, 1.0)),
                               ('ball', _ball)):
                builder = render3d.Builder()
                make(builder)
                self.meshes[name] = builder.build(self.stage.program,
                                                  self.stage.depth_program)

    def close(self) -> None:
        if type(self).instance is self:
            for mesh in self.meshes.values():
                mesh.delete()
            self.meshes = {}
            self.stage.close()
        super().close()

    # --- the play ----------------------------------------------------------

    def _make_run(self):
        return model.Run(model.deal(self.rung, rng=self.rng))

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        self.message = run.board.question
        self._tones_live(run.notes, model.patches(run.board),
                         run.level.seconds + 5.0)
        return ok

    def _held(self):
        k = self.keys
        on = set()
        for symbol, port in ((key.LEFT, model.FACE_LEFT),
                             (key.RIGHT, model.FACE_RIGHT),
                             (key.UP, model.FACE_UP),
                             (key.DOWN, model.FACE_DOWN),
                             (key.A, model.LEFT), (key.D, model.RIGHT),
                             (key.W, model.UP), (key.S, model.DOWN)):
            if k[symbol]:
                on.add(port)
        return frozenset(on) if on else None

    def on_mouse_motion(self, x, y, dx, dy):
        self._point(x, y)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._point(x, y)

    def _point(self, x: float, y: float) -> None:
        """The mouse, taken through the lens onto the paddle's plane."""
        run = self.run
        if run is None or self.phase != self.PLAY or self.view_proj is None:
            return
        left, bottom, width, height = self.rect
        nx = (x - left) / max(1.0, width) * 2 - 1
        ny = (y - bottom) / max(1.0, height) * 2 - 1
        back = ~self.view_proj
        a = back @ Vec4(nx, ny, -1.0, 1.0)
        b = back @ Vec4(nx, ny, 1.0, 1.0)
        a = (a.x / a.w, a.y / a.w, a.z / a.w)
        b = (b.x / b.w, b.y / b.w, b.z / b.w)
        if abs(b[2] - a[2]) < 1e-9:
            return
        t = -a[2] / (b[2] - a[2])
        run.point(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    # --- layout ------------------------------------------------------------

    def _stage_rect(self) -> Tuple[float, float, float, float]:
        window_w, _window_h = pixel_size()
        bottom = above_the_band(from_bottom_edge(58))
        top = from_top_edge(110)
        return (window_w * 0.03, bottom, window_w * 0.94,
                max(48.0, top - bottom))

    def _camera(self, aspect: float):
        fov = 40.0
        need_h = (H + 0.14) / math.tan(math.radians(fov / 2))
        need_w = (W + 0.14) / (math.tan(math.radians(fov / 2))
                               * max(aspect, 0.3))
        eye = (0.0, 0.12, max(need_h, need_w))
        look = Mat4.look_at(Vec3(*eye), Vec3(0.0, 0.0, -D * 0.5),
                            Vec3(0.0, 1.0, 0.0))
        proj = Mat4.perspective_projection(aspect, 0.1, 30.0, fov=fov)
        return proj @ look, eye

    def _see(self, p) -> Optional[Tuple[float, float]]:
        """A point of the box on the screen."""
        c = self.view_proj @ Vec4(p[0], p[1], p[2], 1.0)
        if c.w <= 1e-6:
            return None
        left, bottom, width, height = self.rect
        return (left + (c.x / c.w + 1) / 2 * width,
                bottom + (c.y / c.w + 1) / 2 * height)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.rect = self._stage_rect()
        self.view_proj, self.eye = self._camera(
            self.rect[2] / max(1.0, self.rect[3]))
        if not self.stage.ok:
            self._text(_('This machine cannot draw in 3D: %s')
                       % (self.stage.trouble or ''), left + width / 2,
                       bottom + height / 2, 14)
            return
        nxt = run.next_order()
        for b in run.bricks:
            if b.order < 0 or any(o.i == b.i and o.j == b.j and o.k > b.k
                                  for o in run.bricks):
                continue             # unnumbered, or hidden behind another
            c, h = run.box(b)
            at = self._see((c[0], c[1], c[2] + h[2]))
            if at is not None:
                self._text(str(b.order + 1), at[0], at[1],
                           calc_fontsize(15 if b.order == nxt else 12),
                           bold=True,
                           colour=(20, 20, 24, 255) if b.order == nxt
                           else (235, 235, 240, 255), group=self.top_group)
        if self.phase == self.PLAY:
            if not run.touched:
                self.message = _('Move the paddle to begin')
            elif any(ball.held > 0 for ball in run.balls):
                self.message = _('Ready...')
            else:
                self.message = run.board.question

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        said = _('rung %d  %d/%d   lives %d   bricks %d   %.0f s') % (
            self.rung, self.trial, self.total_trials, run.lives, run.left(),
            run.remaining())
        if run.level.colours:
            said += '   ' + _('paddle: %s') % NAMES[run.colour]
        return said

    # --- the picture -------------------------------------------------------

    def _add(self, draws, mesh, centre, half, material, tint, turn=None,
             casts=True) -> None:
        m, nscale = render3d.placed(tuple(centre), tuple(half), spin=turn)
        draws.append(render3d.Draw(self.meshes[mesh], m, nscale, material,
                                   tint, False, casts))

    def _draws(self) -> List[render3d.Draw]:
        run = self.run
        d: List[render3d.Draw] = []
        box = lambda c, h, tint, casts=False, material=render3d.CUP: \
            self._add(d, 'box', c, h, material, tint, None, casts)  # noqa: E731
        # The box, and ribs round it to give its depth.
        box((0.0, -H - 0.05, -D / 2), (W + 0.1, 0.05, D / 2 + 0.05), FLOOR)
        box((0.0, H + 0.05, -D / 2), (W + 0.1, 0.05, D / 2 + 0.05), WALL)
        box((-W - 0.05, 0.0, -D / 2), (0.05, H, D / 2 + 0.05), WALL)
        box((W + 0.05, 0.0, -D / 2), (0.05, H, D / 2 + 0.05), WALL)
        box((0.0, 0.0, -D - 0.05), (W + 0.1, H + 0.1, 0.05), BACK)
        for k in range(1, 6):
            z = -D * k / 6.0
            box((0.0, -H + 0.004, z), (W, 0.004, 0.012), RIB)
            box((0.0, H - 0.004, z), (W, 0.004, 0.012), RIB)
            for sx in (-1, 1):
                box((sx * (W - 0.004), 0.0, z), (0.004, H, 0.012), RIB)
        colours = run.level.colours
        nxt = run.next_order()
        for b in run.bricks:
            c, h = run.box(b)
            material = render3d.CUP
            if b.kind == model.STEEL:
                tint, material = STEEL, render3d.STEEL
            elif b.kind == model.MINE:
                tint = MINE
            elif b.kind == model.BOMB:
                tint = BOMB
            else:
                tint = INKS[b.colour if colours else 0]
                if b.order >= 0:
                    tint = LIT if b.order == nxt else \
                        tuple(v * 0.45 for v in tint)
            box(c, h, tint, True, material)
            front = c[2] + h[2]
            if b.kind in (model.MINE, model.BOMB):
                self._add(d, 'ball', (c[0], c[1], front),
                          (0.07, 0.07, 0.07), render3d.CUP,
                          (0.92, 0.12, 0.10) if b.kind == model.MINE
                          else (0.08, 0.08, 0.09))
            for extra in range(b.hits - 1):
                grow = 0.62 - 0.2 * extra
                box((c[0], c[1], front + 0.012 + 0.024 * extra),
                    (h[0] * grow, h[1] * grow, 0.012),
                    tuple(v * 0.7 for v in tint), True)
        for when, c in run.burst:
            age = (run.t - when) / 0.4
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                box((c[0] + sx * 0.16 * age, c[1] + sy * 0.12 * age - 0.2
                     * age * age, c[2] + 0.1 * age),
                    (0.035 * (1 - age),) * 3, LIT)
        for ball in run.balls:
            self._add(d, 'ball', ball.p, (model.BALL,) * 3, render3d.CUP,
                      INKS[ball.colour if colours else 0])
        # The paddle: a frame to see through, and the rod it faces along.
        n, a, up = run.frame()
        pw, ph = run.level.paddle
        turn = Mat4(a[0], a[1], a[2], 0.0, up[0], up[1], up[2], 0.0,
                    -n[0], -n[1], -n[2], 0.0, 0.0, 0.0, 0.0, 1.0)
        tint = INKS[run.colour] if colours else (0.95, 0.80, 0.30)
        centre = (run.px, run.py, 0.0)

        def bar(ox, oy, oz, hx, hy, hz, colour=tint):
            at = tuple(centre[q] + a[q] * ox + up[q] * oy + n[q] * oz
                       for q in range(3))
            self._add(d, 'box', at, (hx, hy, hz), render3d.CUP, colour, turn)
        t = 0.014
        bar(0.0, ph, 0.0, pw + t, t, t)
        bar(0.0, -ph, 0.0, pw + t, t, t)
        bar(pw, 0.0, 0.0, t, ph, t)
        bar(-pw, 0.0, 0.0, t, ph, t)
        bar(0.0, 0.0, 0.0, pw, 0.004, 0.004)
        bar(0.0, 0.0, 0.0, 0.004, ph, 0.004)
        bar(0.0, 0.0, 0.16, 0.006, 0.006, 0.16, (0.96, 0.96, 0.98))
        return d

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        run = self.run
        if run is not None and self.stage.ok and self.view_proj is not None \
                and self.phase in (self.PLAY, 'judged'):
            left, bottom, width, height = self.rect
            window_w, window_h = pixel_size()
            fb_w, fb_h = framebuffer_size(state.window)
            sx = fb_w / float(window_w) if window_w else 1.0
            sy = fb_h / float(window_h) if window_h else 1.0
            hurt = max(0.0, 1.0 - (run.t - run.flash) / 0.35)
            dark = (0.05, 0.05, 0.07) if self.dark else (0.80, 0.82, 0.87)
            backdrop = tuple(v + (c - v) * 0.6 * hurt
                             for v, c in zip(dark, (0.85, 0.15, 0.12)))
            self.stage.render((int(left * sx), int(bottom * sy),
                               int(width * sx), int(height * sy)),
                              self._draws(), self.view_proj, self.eye, LIGHT,
                              (0.0, 0.0, -D / 2), (), backdrop)
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
