# -*- coding: utf-8 -*-
"""Live Claw Machine on screen: the cabinet in real perspective.

The pit, its prizes, the chute and its fence, the gantry on its rails,
the rope and the claw are drawn by the workshop's 3D stage from where
the physics has them, lit from above so that the claw's shadow falls
on the heap under it -- the best cue there is to where it will come
down. There are two windows to look through, the front and the right
side; a player walks from one to the other to line the claw up.

Arrows or WASD drive the gantry (Up is away from you); Space or Enter
is the button; V or Tab walks round to the other window.

For the agent boundary: ports 0-3 drive the gantry left, right, away
and nearer; port 4 is the button; port 5 changes window.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pyglet
from pyglet.math import Mat4, Vec3
from pyglet.window import key

from .. import display, state
from .. import liveclaw as model
from ..geometry import (framebuffer_size, from_bottom_edge, from_top_edge,
                        pixel_size)
from ..i18n import _
from . import render3d
from .clocked import ClockedTask
from .verdict import above_the_band

H, TOP = model.HALF, model.TOP
FELT = (0.20, 0.34, 0.62)
PANEL = (0.90, 0.92, 0.96)
FRAME = (0.80, 0.82, 0.88)
ROPE = (0.92, 0.92, 0.90)
LIGHT = render3d.Light(direction=(0.25, 0.92, 0.3),
                       colour=(1.0, 0.97, 0.92), sky=(0.62, 0.66, 0.74),
                       ground=(0.30, 0.28, 0.27), span=0.75)
SAID = {'aim': _('Steer over a prize and press the button'),
        'lower': _('Down it goes'), 'grip': _('The claw closes'),
        'raise': _('Up'), 'carry': _('Home to the chute'),
        'release': _('The claw opens'), 'over': ''}


def _placed(pos, mat, size) -> Tuple[Mat4, Tuple[float, float, float]]:
    """A model matrix for a solid the engine has at *pos* turned by
    *mat* (nine numbers by rows), its unit mesh scaled by *size*: the
    engine's z-up frame turned into the stage's y-up one."""
    r = mat
    sx, sy, sz = size
    # Rows of C.R, C taking (x, y, z) to (x, z, -y); columns scaled.
    rows = ((r[0] * sx, r[1] * sy, r[2] * sz),
            (r[6] * sx, r[7] * sy, r[8] * sz),
            (-r[3] * sx, -r[4] * sy, -r[5] * sz))
    m = Mat4(rows[0][0], rows[1][0], rows[2][0], 0.0,
             rows[0][1], rows[1][1], rows[2][1], 0.0,
             rows[0][2], rows[1][2], rows[2][2], 0.0,
             pos[0], pos[2], -pos[1], 1.0)
    return m, (1.0 / (sx * sx), 1.0 / (sy * sy), 1.0 / (sz * sz))


IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _along(a, b) -> Tuple[float, ...]:
    """A turn (nine numbers by rows) taking the z axis along a to b."""
    d = [b[k] - a[k] for k in range(3)]
    n = math.sqrt(sum(v * v for v in d)) or 1.0
    z = [v / n for v in d]
    ref = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = [ref[1] * z[2] - ref[2] * z[1], ref[2] * z[0] - ref[0] * z[2],
         ref[0] * z[1] - ref[1] * z[0]]
    n = math.sqrt(sum(v * v for v in x))
    x = [v / n for v in x]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2],
         z[0] * x[1] - z[1] * x[0]]
    return (x[0], y[0], z[0], x[1], y[1], z[1], x[2], y[2], z[2])


def _drum(builder: render3d.Builder, segments: int = 28) -> None:
    """A unit cylinder about the z axis: radius 1, from -1 to 1."""
    for z, nz in ((1.0, 1.0), (-1.0, -1.0)):
        base = len(builder.positions) // 3
        builder.positions.extend((0.0, 0.0, z))
        builder.normals.extend((0.0, 0.0, nz))
        for k in range(segments):
            a = 2 * math.pi * k / segments
            builder.positions.extend((math.cos(a), math.sin(a), z))
            builder.normals.extend((0.0, 0.0, nz))
        for k in range(segments):
            i, j = base + 1 + k, base + 1 + (k + 1) % segments
            builder.indices.extend((base, i, j) if nz > 0 else (base, j, i))
    base = len(builder.positions) // 3
    for k in range(segments):
        a = 2 * math.pi * k / segments
        c, s = math.cos(a), math.sin(a)
        builder.positions.extend((c, s, -1.0))
        builder.normals.extend((c, s, 0.0))
        builder.positions.extend((c, s, 1.0))
        builder.normals.extend((c, s, 0.0))
    for k in range(segments):
        i, j = base + 2 * k, base + 2 * ((k + 1) % segments)
        builder.indices.extend((i, j, j + 1, i, j + 1, i + 1))


def _ball(builder: render3d.Builder, rings: int = 18,
          segments: int = 26) -> None:
    """A unit sphere, wound anticlockwise seen from outside (the
    stage's own is wound for its marble, the other way)."""
    base = len(builder.positions) // 3
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        z, r = math.cos(phi), math.sin(phi)
        for step in range(segments + 1):
            theta = 2.0 * math.pi * step / segments
            p = (r * math.cos(theta), r * math.sin(theta), z)
            builder.positions.extend(p)
            builder.normals.extend(p)
    for ring in range(rings):
        for step in range(segments):
            a = base + ring * (segments + 1) + step
            b = a + segments + 1
            builder.indices.extend((a, b, b + 1, a, b + 1, a + 1))


class LiveClaw(ClockedTask):
    """Win a prize from a real claw machine."""

    instance: Optional['LiveClaw'] = None

    TITLE = 'Live Claw Machine'
    TASK_ID = 'live_claw_machine'
    PREFIX = 'LIVECLAW'
    CATEGORY = 'perception'
    MODEL = model
    SUBSTEP = 1 / 60.0
    FEEDBACK = 2.5
    EVENT_KEYS = {key.SPACE: model.DROP, key.RETURN: model.DROP,
                  key.ENTER: model.DROP, key.V: model.VIEW,
                  key.TAB: model.VIEW}
    FOOTNOTE = _('Arrows / WASD: drive (Up is away)   Space: the button   '
                 'V: the other window   Esc: menu')

    def __init__(self) -> None:
        self.stage = render3d.Stage()
        self.meshes = {}
        super().__init__()
        self._build_meshes()

    def close(self) -> None:
        if type(self).instance is self:
            for mesh in self.meshes.values():
                mesh.delete()
            self.meshes = {}
            self.stage.close()
        super().close()

    # --- meshes ----------------------------------------------------------

    def _build_meshes(self) -> None:
        if not self.stage.ok:
            return
        program, depth = self.stage.program, self.stage.depth_program
        b = render3d.Builder()
        b.box(-1.0, -1.0, -1.0, 1.0, 1.0, 1.0)
        self.meshes['box'] = b.build(program, depth)
        b = render3d.Builder()
        _ball(b)
        self.meshes['ball'] = b.build(program, depth)
        b = render3d.Builder()
        _drum(b)
        self.meshes['drum'] = b.build(program, depth)

    # --- the play --------------------------------------------------------

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = SAID['aim']
        return ok

    def _held(self):
        k = self.keys
        for keys, port in (((key.LEFT, key.A), model.LEFT),
                           ((key.RIGHT, key.D), model.RIGHT),
                           ((key.UP, key.W), model.AWAY),
                           ((key.DOWN, key.S), model.NEAR)):
            if any(k[s] for s in keys):
                return port
        return None

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        if self.phase == self.PLAY:
            self.message = SAID.get(run.phase, '')
        if not self.stage.ok:
            self._text(_('This machine cannot draw in 3D: %s')
                       % (self.stage.trouble or ''), left + width / 2,
                       bottom + height / 2, 14)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        said = _('rung %d  %d/%d') % (self.rung, self.trial, self.total_trials)
        if self.run.phase == 'aim':
            said += _('   %.0f s   %s window') % (
                self.run.left, _('front') if self.run.view == 0 else _('side'))
        return said

    # --- the picture -----------------------------------------------------

    def _stage_rect(self) -> Tuple[int, int, int, int]:
        window_w, window_h = pixel_size()
        bottom = above_the_band(from_bottom_edge(58))
        top = from_top_edge(110)
        left = int(window_w * 0.03)
        width = int(window_w * 0.94)
        height = max(48, top - bottom)
        fb_w, fb_h = framebuffer_size(state.window)
        sx = fb_w / float(window_w) if window_w else 1.0
        sy = fb_h / float(window_h) if window_h else 1.0
        return (int(left * sx), int(bottom * sy), int(width * sx),
                int(height * sy))

    def _camera(self, aspect: float, view: int):
        # A player's eye: a little above the pit's rim, looking down in.
        far = 1.12 if aspect >= 1.0 else 1.12 / max(aspect, 0.4)
        eye = (0.0, 0.8, far) if view == 0 else (far, 0.8, 0.0)
        look = Mat4.look_at(Vec3(*eye), Vec3(0.0, 0.27, 0.0),
                            Vec3(0.0, 1.0, 0.0))
        proj = Mat4.perspective_projection(aspect, 0.05, 8.0, fov=40.0)
        return proj @ look, eye

    def _solid(self, draws, mesh, pos, mat, size, material, tint,
               casts=True) -> None:
        m, nscale = _placed(pos, mat, size)
        draws.append(render3d.Draw(self.meshes[mesh], m, nscale, material,
                                   tint, False, casts))

    def _draws(self, view: int) -> List[render3d.Draw]:
        run = self.run
        d: List[render3d.Draw] = []
        c, f = model.CHUTE, model.FENCE
        box = lambda pos, size, material, tint, casts=True: self._solid(  # noqa: E731
            d, 'box', pos, IDENTITY, size, material, tint, casts)
        # The pit: its floor in two slabs round the chute, the tray below.
        box((c / 2, 0.0, -0.1), (H - c / 2, H, 0.1), render3d.CUP, FELT)
        box((-H + c / 2, c / 2, -0.1), (c / 2, H - c / 2, 0.1),
            render3d.CUP, FELT)
        box((-H + c / 2, -H + c / 2, -0.2), (c / 2, c / 2, 0.01),
            render3d.CUP, (0.05, 0.05, 0.06))
        box((-H + c + 0.005, -H + c / 2, f / 2), (0.005, c / 2 + 0.005, f / 2),
            render3d.CUP, (0.95, 0.82, 0.25))
        box((-H + c / 2, -H + c + 0.005, f / 2), (c / 2, 0.005, f / 2),
            render3d.CUP, (0.95, 0.82, 0.25))
        # The cabinet below the glass, and the walls not looked through.
        box((0.0, 0.0, -0.32), (H + 0.03, H + 0.03, 0.105), render3d.CUP,
            (0.72, 0.16, 0.2))
        box((0.0, H + 0.012, 0.36), (H + 0.024, 0.012, 0.36), render3d.CUP,
            PANEL, False)
        side = -1 if view == 1 else 1
        if view == 0:
            for sx in (-1, 1):
                box((sx * (H + 0.012), 0.0, 0.36), (0.012, H, 0.36),
                    render3d.CUP, PANEL, False)
        else:
            box((-H - 0.012, 0.0, 0.36), (0.012, H, 0.36), render3d.CUP,
                PANEL, False)
            box((0.0, -H - 0.012, 0.36), (H + 0.024, 0.012, 0.36),
                render3d.CUP, PANEL, False)
        del side
        # The gantry: two rails, the beam that runs on them, the winch.
        for sx in (-1, 1):
            box((sx * (H - 0.01), 0.0, TOP + 0.05), (0.012, H, 0.012),
                render3d.STEEL, FRAME)
        if run is not None:
            box((0.0, run.y, TOP + 0.03), (H, 0.014, 0.012), render3d.STEEL,
                FRAME)
            box((run.x, run.y, TOP + 0.012), (0.04, 0.035, 0.022),
                render3d.CUP, (0.25, 0.26, 0.3))
            a, b = run.rope_ends()
            mid = tuple((a[k] + b[k]) / 2 for k in range(3))
            length = math.sqrt(sum((a[k] - b[k]) ** 2 for k in range(3)))
            self._solid(d, 'drum', mid, _along(a, b),
                        (0.0022, 0.0022, length / 2), render3d.CUP, ROPE)
            for s in run.shapes():
                if s.part == 'gold':
                    material, tint = render3d.BRASS, s.colour
                elif s.part == 'prize':
                    material, tint = render3d.CUP, s.colour
                else:
                    material, tint = render3d.CUP, s.colour
                mesh = {'box': 'box', 'ball': 'ball', 'drum': 'drum',
                        'rod': 'drum'}[s.kind]
                self._solid(d, mesh, s.pos, s.mat, s.size, material, tint)
        return d

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        if self.run is not None and self.stage.ok \
                and self.phase in (self.PLAY, 'judged'):
            rect = self._stage_rect()
            aspect = rect[2] / float(max(1, rect[3]))
            view_proj, eye = self._camera(aspect, self.run.view)
            backdrop = ((0.07, 0.07, 0.09) if self.dark
                        else (0.88, 0.89, 0.92))
            self.stage.render(rect, self._draws(self.run.view), view_proj,
                              eye, LIGHT, (0.0, 0.3, 0.0), (), backdrop)
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
