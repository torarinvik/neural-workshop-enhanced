# -*- coding: utf-8 -*-
"""Shadow Play on screen: a copper rod, a lamplit wall, and outlines.

A plaster wall at the back of a small room, warm with lamplight; the
copper rod hangs in the middle of the room and its shadow falls on the
wall, soft and dark. A gold outline on the wall is the shadow wanted.
On the floor-lamp rungs a second shadow lies on the floor with its own
outline. Drag the rod to turn it (sideways about the upright, up and
down to tip it, with the right button or Shift to roll it), or use
A / D, W / S and Q / E (or the arrow keys). A bar below shows how
close the fit is; it fills green while the fit is held.

For the agent boundary: ports 0-5 turn the rod for one step: about the
upright left and right, tipping down and up, rolling left and right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key, mouse

from .. import shadowplay as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .lens import Lens
from .pointer import Pointer
from .tones import Tones, patch

COPPER = (214, 128, 70)
GOLD = (255, 206, 90)
DRAG = 0.012                  # radians a pixel of drag


class ShadowPlay(Pointer, Tones, ClockedTask):
    """Turn the rod until its shadow fits the outline."""

    instance: Optional['ShadowPlay'] = None

    TITLE = 'Shadow Play'
    TASK_ID = 'shadow_play'
    PREFIX = 'SHADOW'
    CATEGORY = 'perception'
    FEEDBACK = 2.5
    MODEL = model
    FOOTNOTE = _('Drag to turn (right button or Shift: roll)   '
                 'A D / W S / Q E or arrows   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        level = self.run.level
        which = {1: _('Turn it left and right'),
                 2: _('Turn and tip it'),
                 3: _('Turn, tip and roll it')}[level.axes]
        self.message = which + _(' until the shadow fits the outline')
        self._tones_live(self.run.notes, [patch('sine', 1), patch('bell', 2)],
                         level.seconds + 1.0)
        return ok

    def _held(self):
        k = self.keys
        on = set()
        for keys, port in (((key.LEFT, key.A), model.YAW_L),
                           ((key.RIGHT, key.D), model.YAW_R),
                           ((key.UP, key.W), model.PITCH_U),
                           ((key.DOWN, key.S), model.PITCH_D),
                           ((key.Q,), model.ROLL_L),
                           ((key.E,), model.ROLL_R)):
            if any(k[s] for s in keys):
                on.add(port)
        return on or None

    def _drag(self, dx, dy, buttons, modifiers) -> None:
        run = self.run
        if buttons & mouse.RIGHT or modifiers & key.MOD_SHIFT:
            run.rotate(2, -dx * DRAG)
            return
        run.rotate(1, dx * DRAG)
        run.rotate(0, -dy * DRAG)

    # --- drawing ------------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        d, batch = self.drawn, self.batch
        setup = run.setup
        level = run.level
        Wx, Wy, NEAR = 3.4, 2.4, 1.8
        lens = Lens((0.5, 0.7, 5.6), (0.0, -0.35, -1.0), 1.0, 0.0, 0.0)
        Z0, F0 = -model.WALL, -model.FLOOR
        lens.fit(((-Wx, Wy, Z0), (Wx, Wy, Z0), (-Wx, F0, NEAR),
                  (Wx, F0, NEAR)), left, bottom + 20, width, height - 20,
                 margin=0.02)
        focal = lens.focal
        g = [pyglet.graphics.Group(order=-14 + k) for k in range(6)]
        polish.card(d, batch, left - 4, bottom - 4, width + 8, height + 8,
                    (36, 30, 34), radius=14, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        Z, F = Z0, F0

        def pts(*ps):
            out = []
            for p in ps:
                q = lens.see(p)
                if q is None:
                    return None
                out.append((q[0], q[1]))
            return out

        def poly(ps, colour, group):
            if ps:
                d.append(pyglet.shapes.Polygon(*ps, color=colour,
                                               batch=batch, group=group))
        # The room: wall, floor, and the lamplight on the wall.
        light = model.wall_light(level.swing, run.t)
        bands = 10
        for k in range(bands):
            y0 = F + (Wy - F) * k / bands
            y1 = F + (Wy - F) * (k + 1) / bands
            poly(pts((-Wx, y0, Z), (Wx, y0, Z), (Wx, y1, Z), (-Wx, y1, Z)),
                 polish.mix((150, 132, 120), (214, 196, 170),
                            1 - abs(k - bands * 0.55) / bands), g[0])
        centre = lens.see(model.on_wall((0.0, 0.0, 0.0), light))
        if centre:
            polish.glow(d, batch, centre[0], centre[1], focal * 0.28,
                        (255, 230, 170), strength=120, group=g[1])
        for k in range(8):
            z0 = Z + (NEAR - Z) * k / 8
            z1 = Z + (NEAR - Z) * (k + 1) / 8
            poly(pts((-Wx, F, z0), (Wx, F, z0), (Wx, F, z1), (-Wx, F, z1)),
                 polish.mix((110, 80, 60), (150, 108, 76), k / 8), g[0])
        edge = pts((-Wx, F, Z), (Wx, F, Z))
        if edge:
            d.append(pyglet.shapes.Line(*edge[0], *edge[1], thickness=3,
                                        color=(80, 60, 50), batch=batch,
                                        group=g[1]))
        # Outlines, then shadows.
        want = model.target_at(setup, run.t)
        rod = setup.rod
        fits = run.fit <= level.tol

        def cast(turn, floor):
            out = []
            for a, b in rod:
                pa = model.app(turn, a)
                pb = model.app(turn, b)
                if floor:
                    qa, qb = model.on_floor(pa), model.on_floor(pb)
                else:
                    qa, qb = model.on_wall(pa, light), model.on_wall(pb, light)
                seg = pts(qa, qb)
                if seg:
                    out.append((seg, lens.see(qa)[2]))
            return out
        planes = [False] + ([True] if level.floor else [])
        for floor in planes:
            for (a, b), depth in cast(want, floor):
                w = lens.size(0.16, depth)
                d.append(pyglet.shapes.Line(*a, *b, thickness=w * 2.2,
                                            color=GOLD + (60,), batch=batch,
                                            group=g[2]))
                d.append(pyglet.shapes.Line(*a, *b, thickness=max(2.0, w * 0.4),
                                            color=GOLD + (220,), batch=batch,
                                            group=g[3]))
            for (a, b), depth in cast(run.turn, floor):
                w = lens.size(0.11, depth)
                colour = (40, 90, 50, 190) if fits else (40, 30, 46, 175)
                d.append(pyglet.shapes.Line(*a, *b, thickness=w, color=colour,
                                            batch=batch, group=g[4]))
                for p in (a, b):
                    d.append(pyglet.shapes.Circle(*p, w / 2, color=colour,
                                                  batch=batch, group=g[4]))
        # The rod, far parts first.
        segs = []
        for a, b in rod:
            pa, pb = model.app(run.turn, a), model.app(run.turn, b)
            sa, sb = lens.see(pa), lens.see(pb)
            if sa and sb:
                dirn = tuple(pb[i] - pa[i] for i in range(3))
                n = math.sqrt(sum(x * x for x in dirn)) or 1.0
                lit = abs(sum(dirn[i] / n * light[i] for i in range(3)))
                segs.append(((sa[2] + sb[2]) / 2, sa, sb, lit))
        segs.sort(key=lambda s: -s[0])
        for k, (depth, sa, sb, lit) in enumerate(segs):
            grp = pyglet.graphics.Group(order=k + 1)
            w = lens.size(0.13, depth)
            base = polish.mix(COPPER, (90, 50, 30), 0.55 * lit)
            d.append(pyglet.shapes.Line(sa[0], sa[1], sb[0], sb[1],
                                        thickness=w, color=base, batch=batch,
                                        group=grp))
            d.append(pyglet.shapes.Line(sa[0], sa[1] + w * 0.2, sb[0],
                                        sb[1] + w * 0.2,
                                        thickness=max(1.0, w * 0.3),
                                        color=polish.lighter(COPPER, 0.45),
                                        batch=batch, group=grp))
            for s in (sa, sb):
                d.append(pyglet.shapes.Circle(s[0], s[1], w * 0.55,
                                              color=polish.darker(base, 0.1),
                                              batch=batch, group=grp))
        # How close, and the hold.
        bx, by, bw = left + width * 0.3, bottom + 14, width * 0.4
        top = pyglet.graphics.Group(order=60)
        polish.rounded(d, batch, bx, by, bw, 10, (255, 255, 255, 60),
                       radius=5, group=top)
        close = run.close()
        polish.rounded(d, batch, bx, by, max(10.0, bw * close), 10,
                       polish.mix((236, 90, 70), (110, 230, 140), close),
                       radius=5, group=pyglet.graphics.Group(order=61))
        if run.fit_since is not None:
            share = min(1.0, (run.t - run.fit_since) / level.hold)
            d.append(pyglet.shapes.Arc(bx + bw + 20, by + 5, 10, thickness=4,
                                       angle=360 * share, start_angle=90,
                                       color=(110, 240, 150), batch=batch,
                                       group=top))
        left_t = max(0.0, level.seconds - run.t)
        self._text('%d' % math.ceil(left_t), bx - 24, by + 5, 11, bold=True,
                   colour=(255, 255, 255, 220), group=top)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
