# -*- coding: utf-8 -*-
"""3D Matrix on screen: nine cells and the answers, each a small scene
drawn by the workshop's 3D stage -- lit, shaded, casting shadows -- so
that what is in front of what, and what is seen from where, has to be
read the way it is from a photograph.

Click an answer or press its number.

For the agent boundary: port k picks answer k + 1.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import pyglet
from pyglet.math import Mat4, Vec3

from .. import display, state
from .. import matrix3d as model
from ..geometry import calc_fontsize, framebuffer_size, pixel_size
from ..i18n import _
from . import render3d
from .spacetask import ChoiceTask

LIGHT = render3d.Light(direction=(0.05, 0.76, 0.65),
                       colour=(1.0, 0.98, 0.95), sky=(0.66, 0.68, 0.74),
                       ground=(0.36, 0.35, 0.36), span=3.4)
TABLE_LIGHT, TABLE_DARK = (0.90, 0.90, 0.93), (0.20, 0.20, 0.24)


def _placed(pos, mat, size) -> Tuple[Mat4, Tuple[float, float, float]]:
    """A model matrix for a unit mesh scaled by *size*, turned by *mat*
    (nine numbers by rows) and set at *pos*: the model's z-up frame
    turned into the stage's y-up one."""
    r = mat
    sx, sy, sz = size
    rows = ((r[0] * sx, r[1] * sy, r[2] * sz),
            (r[6] * sx, r[7] * sy, r[8] * sz),
            (-r[3] * sx, -r[4] * sy, -r[5] * sz))
    m = Mat4(rows[0][0], rows[1][0], rows[2][0], 0.0,
             rows[0][1], rows[1][1], rows[2][1], 0.0,
             rows[0][2], rows[1][2], rows[2][2], 0.0,
             pos[0], pos[2], -pos[1], 1.0)
    return m, (1.0 / (sx * sx), 1.0 / (sy * sy), 1.0 / (sz * sz))


def _triangle(builder, points, normals) -> None:
    """One triangle, wound anticlockwise seen from where its normals
    point (the stage lights the side a triangle is wound towards)."""
    a, b, c = points
    u = [b[k] - a[k] for k in range(3)]
    v = [c[k] - a[k] for k in range(3)]
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0])
    mean = [sum(n[k] for n in normals) for k in range(3)]
    if sum(cross[k] * mean[k] for k in range(3)) < 0:
        points = (a, c, b)
        normals = (normals[0], normals[2], normals[1])
    base = len(builder.positions) // 3
    for p, n in zip(points, normals):
        builder.positions.extend(p)
        builder.normals.extend(n)
    builder.indices.extend((base, base + 1, base + 2))


def _flat(builder, points: Sequence, normal) -> None:
    """A flat convex face."""
    for k in range(1, len(points) - 1):
        _triangle(builder, (points[0], points[k], points[k + 1]),
                  (normal,) * 3)


def _lathe(builder, profile: Sequence[Tuple[float, float]],
           smooth: bool = False, segments: int = 40) -> None:
    """A solid of revolution about the z axis from a profile of
    (radius, z) points running up its outside. *smooth* takes each
    point's own direction for its normal (a ball)."""
    for (r0, z0), (r1, z1) in zip(profile, profile[1:]):
        dr, dz = r1 - r0, z1 - z0
        length = math.hypot(dr, dz) or 1.0
        nr, nz = dz / length, -dr / length
        for k in range(segments):
            a0 = 2 * math.pi * k / segments
            a1 = 2 * math.pi * (k + 1) / segments
            corners, normals = [], []
            for r, z, a in ((r0, z0, a0), (r1, z1, a0), (r1, z1, a1),
                            (r0, z0, a1)):
                c, s = math.cos(a), math.sin(a)
                corners.append((r * c, r * s, z))
                if smooth:
                    m = math.hypot(r, z) or 1.0
                    normals.append((r * c / m, r * s / m, z / m))
                else:
                    normals.append((nr * c, nr * s, nz))
            if r0 > 1e-9:
                _triangle(builder, (corners[0], corners[1], corners[3]),
                          (normals[0], normals[1], normals[3]))
            if r1 > 1e-9:
                _triangle(builder, (corners[1], corners[2], corners[3]),
                          (normals[1], normals[2], normals[3]))


def _wedge(builder) -> None:
    """A ramp filling the unit box: full height at x = -1, none at +1."""
    a, b, c = (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (-1.0, -1.0, 1.0)
    a2, b2, c2 = (-1.0, 1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, 1.0)
    _flat(builder, (a, b, c), (0.0, -1.0, 0.0))
    _flat(builder, (a2, b2, c2), (0.0, 1.0, 0.0))
    _flat(builder, (a, b, b2, a2), (0.0, 0.0, -1.0))
    _flat(builder, (a, a2, c2, c), (-1.0, 0.0, 0.0))
    s = math.sqrt(0.5)
    _flat(builder, (b, b2, c2, c), (s, 0.0, s))


MESHES = {
    'ball': lambda b: _lathe(b, [(math.sin(math.pi * k / 20),
                                  -math.cos(math.pi * k / 20))
                                 for k in range(21)], smooth=True),
    'drum': lambda b: _lathe(b, [(0.0, -1.0), (1.0, -1.0), (1.0, 1.0),
                                 (0.0, 1.0)]),
    'tub': lambda b: _lathe(b, [(0.0, -1.0), (1.0, -1.0), (0.62, 1.0),
                                (0.0, 1.0)]),
    'cone': lambda b: _lathe(b, [(0.0, -1.0), (1.0, -1.0), (0.0, 1.0)]),
    'ring': lambda b: _lathe(b, [(0.82, -1.0), (1.0, -1.0), (1.0, 1.0),
                                 (0.82, 1.0), (0.82, -1.0)], segments=64),
    'wedge': _wedge,
    'box': lambda b: b.box(-1.0, -1.0, -1.0, 1.0, 1.0, 1.0),
}


class Matrix3D(ChoiceTask):
    """Which construction completes the matrix?"""

    instance: Optional['Matrix3D'] = None

    TITLE = '3D Matrix'
    TASK_ID = 'matrix_3d'
    PREFIX = 'MATRIX3D'
    CATEGORY = 'reasoning'
    BUTTONS = 0

    def __init__(self) -> None:
        self.stage = render3d.Stage()
        self.meshes = {}
        self.panels: List[Tuple[float, float, float, float,
                                model.Build]] = []
        super().__init__()
        if self.stage.ok:
            for name, make in MESHES.items():
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

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _verdict(self, right: bool) -> str:
        return '%s %d' % (_('Right:') if right else _('No:'),
                          self.puzzle.answer + 1)

    def _facts(self) -> str:
        said = super()._facts()
        if self.puzzle is not None and self.phase == 'judged':
            said += '   ' + model.explain(self.puzzle)
        return said

    # --- layout ----------------------------------------------------------

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        self.panels = []
        n = len(p.options)
        cols = 2 if n <= 4 else 3
        rows = (n + cols - 1) // cols
        between = 0.45                       # of a cell, matrix to answers
        s = min(height / 3.0, width / (3 + between + cols))
        pad = max(2.0, s * 0.03)
        x0 = left + (width - s * (3 + between + cols)) / 2
        top = bottom + (height + 3 * s) / 2
        frame = (120, 124, 136)
        for i in range(9):
            r, c = divmod(i, 3)
            x, y = x0 + c * s, top - (r + 1) * s
            self.drawn.append(pyglet.shapes.Box(
                x + pad / 2, y + pad / 2, s - pad, s - pad, thickness=2,
                color=frame, batch=self.batch, group=self.text_group))
            if i < 8:
                self.panels.append((x + pad, y + pad, s - 2 * pad,
                                    s - 2 * pad, p.cells[i]))
            elif self.phase == 'judged':
                self.panels.append((x + pad, y + pad, s - 2 * pad,
                                    s - 2 * pad, p.cells[8]))
            else:
                self._text('?', x + s / 2, y + s / 2, s * 0.32, bold=True)
        ax = x0 + (3 + between) * s
        atop = bottom + (height + rows * s) / 2
        for i, build in enumerate(p.options):
            r, c = divmod(i, cols)
            x, y = ax + c * s, atop - (r + 1) * s
            border, thick = self._mark(i)
            self.drawn.append(pyglet.shapes.Box(
                x + pad / 2, y + pad / 2, s - pad, s - pad,
                thickness=max(2, thick), color=border if thick > 2
                else frame, batch=self.batch, group=self.text_group))
            self._text(str(i + 1), x + pad + 7, y + s - pad - 6,
                       calc_fontsize(13), anchor='left', anchor_y='top',
                       bold=True, group=self.top_group)
            inset = pad + (thick if thick > 2 else 0)
            self.panels.append((x + inset, y + inset, s - 2 * inset,
                                s - 2 * inset, build))
            self.hits.append((x, y, s, s, lambda k=i: self.choose(k)))
        if not self.stage.ok:
            self._text(_('This machine cannot draw in 3D: %s')
                       % (self.stage.trouble or ''), left + width / 2,
                       bottom + height / 2, 14)

    # --- the picture -----------------------------------------------------

    def _camera(self, view: int, extent: float):
        """Every cell of one matrix is framed alike, so sizes compare."""
        around, above = (math.radians(v) for v in model.VIEWS[view])
        target = (0.0, (extent - 0.5) / 2, 0.0)
        far = max(extent * 0.54, 1.78) / math.tan(math.radians(15.0))
        eye = (target[0] + far * math.sin(around) * math.cos(above),
               target[1] + far * math.sin(above),
               target[2] + far * math.cos(around) * math.cos(above))
        look = Mat4.look_at(Vec3(*eye), Vec3(*target), Vec3(0.0, 1.0, 0.0))
        proj = Mat4.perspective_projection(1.0, 0.5, 60.0, fov=30.0)
        return proj @ look, eye

    def _draws(self, build: model.Build, table) -> List[render3d.Draw]:
        m, nscale = _placed((0.0, 0.0, -0.5), model.IDENTITY,
                            (30.0, 30.0, 0.5))
        draws = [render3d.Draw(self.meshes['box'], m, nscale, render3d.CUP,
                               table, False, False)]
        for part in model.parts(build):
            m, nscale = _placed(part.pos, part.mat, part.size)
            draws.append(render3d.Draw(self.meshes[part.mesh], m, nscale,
                                       render3d.CUP, part.colour))
        return draws

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        if self.puzzle is not None and self.stage.ok and self.panels \
                and self.phase in (self.PLAY, 'judged'):
            p = self.puzzle
            window_w, window_h = pixel_size()
            fb_w, fb_h = framebuffer_size(state.window)
            sx = fb_w / float(window_w) if window_w else 1.0
            sy = fb_h / float(window_h) if window_h else 1.0
            extent = max(2.9, max(model.tall(b) for b in
                                  p.cells + p.options) + 0.3)
            table = TABLE_DARK if self.dark else TABLE_LIGHT
            side = int(min(self.panels[0][2] * sx, self.panels[0][3] * sy))
            for x, y, w, h, build in self.panels:
                # One size for every panel: the stage keeps its targets.
                rect = (int(x * sx + (w * sx - side) / 2),
                        int(y * sy + (h * sy - side) / 2), side, side)
                view_proj, eye = self._camera(build.view, extent)
                self.stage.render(rect, self._draws(build, table), view_proj,
                                  eye, LIGHT, (0.0, 1.2, 0.0), (), table)
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
