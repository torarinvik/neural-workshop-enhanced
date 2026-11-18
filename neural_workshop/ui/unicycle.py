# -*- coding: utf-8 -*-
"""Unicycle on screen: a lit 3D field, the camera riding behind.

The field, the rider and the flags are solid, lit meshes with shadows,
drawn by :mod:`neural_workshop.ui.render3d`; the camera follows behind
the rider and swings round with them as they turn. A map in the corner
shows the flags, and a gauge the rider's lean seen from above.

Up / Down pedals and back-pedals; W / S leans forward and back; Left /
Right (or A / D) leans left and right, which also turns the wheel that
way. Hold a pedal key and a lean key together to do both.

For the agent boundary: ports 0-1 pedal and back-pedal, 2-3 lean back
and forward, 4-7 pedal or back-pedal while leaning back or forward, 8-9
lean left and right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.math import Mat4, Vec3
from pyglet.window import key

from .. import display, state
from .. import unicycle as model
from ..geometry import framebuffer_size, pixel_size
from ..i18n import _
from . import render3d
from .livetask import LiveTask

LIGHT = render3d.Light(direction=(0.35, 0.82, 0.45),
                       colour=(1.0, 0.97, 0.90), sky=(0.75, 0.85, 0.95),
                       ground=(0.45, 0.50, 0.36), span=9.0)
SKY = (0.62, 0.78, 0.93)
GRASS = ((0.36, 0.60, 0.27), (0.31, 0.53, 0.24))
ROCK = (0.55, 0.53, 0.50)
SHIRT, TROUSERS, SKIN = (0.95, 0.42, 0.26), (0.25, 0.36, 0.75), \
    (0.98, 0.82, 0.70)
TYRE, RIM, POLE = (0.12, 0.12, 0.14), (0.78, 0.80, 0.84), (0.30, 0.30, 0.34)
NEXT, DONE, LATER = (1.0, 0.30, 0.22), (0.55, 0.55, 0.55), \
    (0.95, 0.92, 0.80)
CELL = 2                       # ground grid cells per mesh quad


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1e-9
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _basis(x, y, z) -> Mat4:
    """A rotation whose columns are *x*, *y* and *z*."""
    return Mat4(x[0], x[1], x[2], 0.0, y[0], y[1], y[2], 0.0,
                z[0], z[1], z[2], 0.0, 0.0, 0.0, 0.0, 1.0)


def _ball(builder: render3d.Builder, rings: int = 12,
          segments: int = 18) -> None:
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


def _wheel(builder: render3d.Builder, segments: int = 28) -> None:
    """A unit cylinder along x: the tyre's tread and its two faces."""
    for k in range(segments):
        a0 = 2 * math.pi * k / segments
        a1 = 2 * math.pi * (k + 1) / segments
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), \
            math.sin(a1)
        n = (0.0, math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2))
        builder.face(((1, c0, s0), (1, c1, s1), (-1, c1, s1),
                      (-1, c0, s0)), n)
        for side in (1, -1):
            quad = ((side, 0, 0), (side, 0, 0), (side, c1, s1),
                    (side, c0, s0))
            if side < 0:
                quad = tuple(reversed(quad))
            builder.face(quad, (float(side), 0.0, 0.0))


class Unicycle(LiveTask):
    """Ride to the flags on one wheel."""

    instance: Optional['Unicycle'] = None

    TITLE = 'Unicycle'
    TASK_ID = 'unicycle'
    PREFIX = 'UNI'
    CATEGORY = 'planning'
    MODEL = model
    BACK = (150, 200, 235)
    FOOTNOTE = _('Up / Down: pedal   W / S: lean forward / back   '
                 'Left / Right: lean and turn   Esc: menu')

    def __init__(self) -> None:
        self.stage = render3d.Stage()
        self.meshes: Dict[str, render3d.Mesh] = {}
        self.field: List[Tuple[render3d.Mesh, tuple, int]] = []
        self.field_of = None
        self.view_proj: Optional[Mat4] = None
        self.eye = (0.0, 0.0, 0.0)
        self.look_at = (0.0, 0.0, 0.0)
        self.area_3d = (0.0, 0.0, 1.0, 1.0)
        self.cam_heading = 0.0
        super().__init__()
        if self.stage.ok:
            for name, make in (('box', lambda b: b.box(-1.0, -1.0, -1.0,
                                                       1.0, 1.0, 1.0)),
                               ('ball', _ball), ('wheel', _wheel)):
                builder = render3d.Builder()
                make(builder)
                self.meshes[name] = builder.build(self.stage.program,
                                                  self.stage.depth_program)

    def close(self) -> None:
        if type(self).instance is self:
            self._drop_field()
            for mesh in self.meshes.values():
                mesh.delete()
            self.meshes = {}
            self.stage.close()
        super().close()

    def _drop_field(self) -> None:
        for mesh, _tint, _material in self.field:
            mesh.delete()
        self.field = []
        self.field_of = None

    # --- the play ----------------------------------------------------------

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Ride to each flag. Keep your head off the ground')
        self.flip = 0
        self.cam_heading = 0.0
        return ok

    def _held(self):
        k = self.keys
        drive = (1 if k[key.UP] else 0) - (1 if k[key.DOWN] else 0)
        lean = (1 if k[key.W] else 0) - (1 if k[key.S] else 0)
        side = (1 if k[key.RIGHT] or k[key.D] else 0) - \
            (1 if k[key.LEFT] or k[key.A] else 0)
        table = {(0, 0): None, (1, 0): model.PEDAL, (-1, 0): model.BACK,
                 (0, -1): model.LEAN_B, (0, 1): model.LEAN_F,
                 (1, -1): model.PEDAL_B, (1, 1): model.PEDAL_F,
                 (-1, -1): model.BACK_B, (-1, 1): model.BACK_F}
        rest = table[(drive, lean)]
        if not side:
            return rest
        sideways = model.LEAN_R if side > 0 else model.LEAN_L
        if rest is None:
            return sideways
        # both wanted: one each step, turn about
        self.flip = getattr(self, 'flip', 0) + 1
        return sideways if self.flip % 2 else rest

    # --- the field, built once a ride ---------------------------------------

    def _build_field(self, tr) -> None:
        self._drop_field()
        if not self.stage.ok:
            return
        grass = [render3d.Builder(), render3d.Builder()]
        rocks = render3d.Builder()
        step = model.DX * CELL
        nx = (tr.nx - 1) // CELL
        nz = (tr.nz - 1) // CELL

        def at(i, j):
            x, z = tr.x0 + i * step, tr.z0 + j * step
            return (x, model.height(tr, x, z), z)
        for j in range(nz):
            for i in range(nx):
                a, b = at(i, j), at(i + 1, j)
                c, d = at(i + 1, j + 1), at(i, j + 1)
                # the normal of the quad, from its diagonals
                n = _unit(_cross((d[0] - b[0], d[1] - b[1], d[2] - b[2]),
                                 (c[0] - a[0], c[1] - a[1], c[2] - a[2])))
                if n[1] < 0:
                    n = (-n[0], -n[1], -n[2])
                grass[(i // 4 + j // 4) % 2].face((d, c, b, a), n)
        draw = random.Random(len(tr.heights) * 31 + tr.nx)
        width, depth = (tr.nx - 1) * model.DX, (tr.nz - 1) * model.DX
        for _k in range(int(width * depth / 9.0)):
            x = tr.x0 + draw.uniform(0, width)
            z = tr.z0 + draw.uniform(0, depth)
            if math.hypot(x, z) < 2.0:
                continue
            s = draw.uniform(0.05, 0.16)
            y = model.height(tr, x, z)
            rocks.box(x - s, y - s * 0.3, z - s, x + s, y + s, z + s * 0.8)
        for builder, tint in ((grass[0], GRASS[0]), (grass[1], GRASS[1]),
                              (rocks, ROCK)):
            if not builder.empty:
                self.field.append((builder.build(self.stage.program,
                                                 self.stage.depth_program),
                                   tint, render3d.CUP))
        self.field_of = tr

    # --- the picture --------------------------------------------------------

    def _add(self, draws, mesh, centre, half, tint, turn=None,
             material=render3d.CUP) -> None:
        m, nscale = render3d.placed(tuple(centre), tuple(half), spin=turn)
        draws.append(render3d.Draw(self.meshes[mesh], m, nscale, material,
                                   tint, False, True))

    def _limb(self, draws, a, b, thick, tint) -> None:
        """A bar from *a* to *b*."""
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        length = math.sqrt(sum(c * c for c in d))
        if length < 1e-6:
            return
        y = tuple(c / length for c in d)
        ref = (0.0, 0.0, 1.0) if abs(y[2]) < 0.9 else (1.0, 0.0, 0.0)
        x = _unit(_cross(y, ref))
        z = _cross(x, y)
        mid = tuple((a[k] + b[k]) / 2 for k in range(3))
        self._add(draws, 'box', mid, (thick, length / 2, thick), tint,
                  _basis(x, y, z))

    def _draws(self) -> List[render3d.Draw]:
        run = self.run
        tr, b = run.tr, run.body
        d: List[render3d.Draw] = []
        ident = Mat4()
        for mesh, tint, material in self.field:
            d.append(render3d.Draw(mesh, ident, (1.0, 1.0, 1.0), material,
                                   tint, False, True))
        # the flags, their cloth square on to the camera
        h = self.cam_heading
        across = (-math.sin(h), 0.0, math.cos(h))
        cloth = _basis(across, (0.0, 1.0, 0.0),
                       (-math.cos(h), 0.0, -math.sin(h)))
        for k, (fx, fz) in enumerate(tr.flags):
            fy = model.height(tr, fx, fz)
            tint = DONE if k < run.flag else NEXT if k == run.flag \
                else LATER
            self._add(d, 'box', (fx, fy + 1.4, fz), (0.04, 1.4, 0.04),
                      (0.92, 0.92, 0.92))
            self._add(d, 'box', (fx + across[0] * 0.45, fy + 2.45,
                                 fz + across[2] * 0.45),
                      (0.45, 0.3, 0.02), tint, cloth)
            if k == run.flag:
                self._add(d, 'ball', (fx, fy + 2.95, fz), (0.12,) * 3,
                          (1.0, 0.85, 0.3))
        # the wheel, tipped with the rider and turning
        f, r, up = model.frame(b)
        c, s = math.cos(b.roll), math.sin(b.roll)
        up_r = tuple(up[k] * c + r[k] * s for k in range(3))
        right_r = tuple(r[k] * c - up[k] * s for k in range(3))
        axle = model.point(tr, b, 0.0)
        turn = _basis(right_r, up_r, tuple(-v for v in f))
        self._add(d, 'wheel', axle, (0.035, model.R, model.R), TYRE, turn)
        self._add(d, 'wheel', axle, (0.04, model.R * 0.72, model.R * 0.72),
                  RIM, turn)
        for k in range(3):
            ang = -b.a + k * math.pi / 3
            spoke = tuple(axle[q] + (f[q] * math.cos(ang) + up_r[q]
                                     * math.sin(ang)) * model.R * 0.7
                          for q in range(3))
            back = tuple(2 * axle[q] - spoke[q] for q in range(3))
            self._limb(d, back, spoke, 0.012, POLE)
        # the rider: seat post, legs to the pedals, body, arms, head
        seat = model.point(tr, b, 1.0)
        top = model.point(tr, b, 1.32)
        head = model.point(tr, b, model.HEAD)
        self._limb(d, axle, seat, 0.025, POLE)
        for k, side in ((0.0, -0.1), (math.pi, 0.1)):
            ang = -b.a + k
            pedal = tuple(axle[q] + (f[q] * math.cos(ang) + up_r[q]
                                     * math.sin(ang)) * 0.16
                          + right_r[q] * side for q in range(3))
            hip = tuple(seat[q] + right_r[q] * side for q in range(3))
            knee = tuple((hip[q] + pedal[q]) / 2 + f[q] * 0.2
                         for q in range(3))
            self._limb(d, hip, knee, 0.06, TROUSERS)
            self._limb(d, knee, pedal, 0.05, TROUSERS)
        self._limb(d, seat, top, 0.13, SHIRT)
        mid = tuple(seat[q] + (top[q] - seat[q]) * 0.85 for q in range(3))
        for side in (-1, 1):
            hand = tuple(mid[q] + right_r[q] * side * 0.55
                         + f[q] * 0.1 - up_r[q] * 0.05 for q in range(3))
            self._limb(d, mid, hand, 0.04, SHIRT)
        self._add(d, 'ball', head, (0.17,) * 3, SKIN)
        return d

    def _camera(self, aspect: float):
        run = self.run
        tr, b = run.tr, run.body
        # the camera swings round after the rider, not at once
        lag = math.atan2(math.sin(b.heading - self.cam_heading),
                         math.cos(b.heading - self.cam_heading))
        self.cam_heading += lag * 0.08
        h = self.cam_heading
        f = (math.cos(h), 0.0, math.sin(h))
        r = (-math.sin(h), 0.0, math.cos(h))
        ground = model.height(tr, b.x, b.z)
        eye = (b.x - f[0] * 4.6 - r[0] * 1.4, ground + 2.5,
               b.z - f[2] * 4.6 - r[2] * 1.4)
        target = (b.x + f[0] * 2.0, ground + 0.9, b.z + f[2] * 2.0)
        view = Mat4.look_at(Vec3(*eye), Vec3(*target), Vec3(0.0, 1.0, 0.0))
        proj = Mat4.perspective_projection(aspect, 0.1, 150.0, fov=58.0)
        # the sun over the camera's shoulder, so the side we see is lit
        self.light = LIGHT._replace(direction=_unit(
            (-f[0] * 0.55 - r[0] * 0.35, 0.8, -f[2] * 0.55 - r[2] * 0.35)))
        return proj @ view, eye, (b.x, ground, b.z)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.order = 0
        self.clip = None
        self.area_3d = (left, bottom, width, height)
        if not self.stage.ok:
            self._text(_('This machine cannot draw in 3D: %s')
                       % (self.stage.trouble or ''), left + width / 2,
                       bottom + height / 2, 14)
            return
        if self.field_of is not run.tr:
            self._build_field(run.tr)
        self.view_proj, self.eye, self.look_at = self._camera(
            width / max(1.0, height))
        tr, b = run.tr, run.body
        # the flags passed, and the time left
        g = self.layer()
        u = max(0.0, min(1.0, run.t / max(1.0, tr.seconds)))
        self.rect(left + 20, bottom + height - 22, (width - 40), 6,
                  (60, 70, 90), g)
        self.rect(left + 20, bottom + height - 22, (width - 40) * (1 - u), 6,
                  (250, 220, 90), g)
        # the map: the flags, and the rider's place and heading
        side = max(70.0, min(width, height) * 0.2)
        x0, y0 = left + 18, bottom + height - side - 40
        self.rect(x0 - 3, y0 - 3, side + 6, side + 6, (40, 60, 40), g)
        self.rect(x0, y0, side, side, (90, 140, 70), g)
        xs = [0.0, b.x] + [p[0] for p in tr.flags]
        zs = [0.0, b.z] + [p[1] for p in tr.flags]
        span = max(max(xs) - min(xs), max(zs) - min(zs), 10.0) * 1.15
        cx, cz = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2

        def on_map(x, z):
            # seen from above, the rider's right (+z when heading +x)
            # is down the map
            return (x0 + side / 2 + (x - cx) / span * side,
                    y0 + side / 2 - (z - cz) / span * side)
        g = self.layer()
        for k, (fx, fz) in enumerate(tr.flags):
            col = tuple(int(255 * v) for v in (
                DONE if k < run.flag else NEXT if k == run.flag else LATER))
            self.disc(on_map(fx, fz), 5 if k == run.flag else 3, col, g)
        me = on_map(b.x, b.z)
        self.line(me, (me[0] + math.cos(b.heading) * 10,
                       me[1] - math.sin(b.heading) * 10), 2,
                  (255, 255, 255), g)
        self.disc(me, 4, (30, 40, 120), g)
        # the lean, seen from above: the dot is the head over the wheel
        g = self.layer()
        rr = max(26.0, min(width, height) * 0.08)
        gx, gy = left + width - rr - 18, bottom + height - rr - 40
        self.disc((gx, gy), rr + 3, (60, 70, 90), g)
        self.disc((gx, gy), rr, (34, 40, 54), g)
        g = self.layer()
        hx, hy, _hz = model.head(tr, b)
        here = model.height(tr, b.x, b.z)
        reach = (hy - here) / (model.POST * model.HEAD + model.R)
        danger = max(0.0, min(1.0, 1.0 - reach))
        fwd = max(-1.0, min(1.0, math.sin(model.tilt(b))))
        sideways = max(-1.0, min(1.0, math.sin(b.roll)))
        self.disc((gx + sideways * rr, gy + fwd * rr), max(4.0, rr * 0.15),
                  (int(120 + 135 * danger), int(240 - 170 * danger), 120), g)

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        run = self.run
        if run is not None and self.stage.ok and self.view_proj is not None \
                and self.field_of is run.tr:
            left, bottom, width, height = self.area_3d
            window_w, window_h = pixel_size()
            fb_w, fb_h = framebuffer_size(state.window)
            sx = fb_w / float(window_w) if window_w else 1.0
            sy = fb_h / float(window_h) if window_h else 1.0
            self.stage.render((int(left * sx), int(bottom * sy),
                               int(width * sx), int(height * sy)),
                              self._draws(), self.view_proj, self.eye,
                              getattr(self, 'light', LIGHT),
                              self.look_at, (), SKY)
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED

    def _facts(self) -> str:
        if self.run is None:
            return ''
        run = self.run
        return _('rung %d  %d/%d   flag %d of %d   %.0f s left') % (
            self.rung, self.trial, self.total_trials,
            min(run.flag + 1, len(run.tr.flags)), len(run.tr.flags),
            max(0.0, run.tr.seconds - run.t))
