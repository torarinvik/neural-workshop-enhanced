# -*- coding: utf-8 -*-
"""The frame shared by the real-time tasks that draw a scene of their own
and may play a sound that follows the run.

It adds to :class:`ClockedTask` the mouse (:class:`Pointer`), sound
(:class:`Tones`), a few plain shapes drawn in order of depth, and
:meth:`LiveTask.stream`, which plays and hands the agent whatever the
model's ``mix(run, t0, t1)`` renders.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import pyglet

from . import polish
from .clocked import ClockedTask
from .pointer import Pointer
from .tones import Tones, patch


class LiveTask(Pointer, Tones, ClockedTask):
    """A clocked task with a scene, the mouse and live sound."""

    FEEDBACK = 2.5
    BACK = (30, 34, 48)

    def __init__(self) -> None:
        super().__init__()
        from .. import state
        state.window.push_handlers(self.on_mouse_scroll)

    def close(self) -> None:
        if type(self).instance is self:
            from .. import state
            try:
                state.window.remove_handlers(self.on_mouse_scroll)
            except Exception:
                pass
        super().close()

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        """The wheel; a task that wants it overrides this."""

    def _deal(self) -> bool:
        ok = super()._deal()
        self.order = 0
        self._sound()
        return ok

    def _sound(self) -> None:
        """Start the run's sound: its ``mix`` if the model has one, else
        its live notes."""
        model, run = self.MODEL, self.run
        if hasattr(model, 'mix'):
            self._tones_stream(lambda t0, t1, run=run: model.mix(run, t0, t1),
                               getattr(run, 'end', 600.0) + 2.0)
        elif hasattr(run, 'notes'):
            self._tones_live(run.notes, [patch(n, k + 1) for k, n in
                                         enumerate(model.PATCHES)],
                             getattr(run, 'end', 600.0) + 2.0)

    # --- drawing, back to front ----------------------------------------------

    def layer(self) -> pyglet.graphics.Group:
        self.order = getattr(self, 'order', 0) + 1
        return pyglet.graphics.Group(order=self.order)

    #: The scene's rectangle, set by :meth:`frame`: shapes are cut to it.
    clip: Optional[Tuple[float, float, float, float]] = None

    def frame(self, left, bottom, width, height, colour=None) -> None:
        self.order = 0
        self.clip = (left, bottom, left + width, bottom + height)
        polish.card(self.drawn, self.batch, left - 4, bottom - 4, width + 8,
                    height + 8, colour or self.BACK, radius=14,
                    shade=(0, 0, 0, 60), group=polish.STAGE)

    def rect(self, x, y, w, h, colour, group) -> None:
        if self.clip is not None:
            x0, y0, x1, y1 = self.clip
            ax, ay = max(x, x0), max(y, y0)
            bx, by = min(x + w, x1), min(y + h, y1)
            if bx <= ax or by <= ay:
                return
            x, y, w, h = ax, ay, bx - ax, by - ay
        self.drawn.append(pyglet.shapes.Rectangle(
            x, y, w, h, color=colour, batch=self.batch, group=group))

    def line(self, a, b, thick, colour, group) -> None:
        if a is None or b is None:
            return
        if self.clip is not None:
            cut = self._cut_line(a, b)
            if cut is None:
                return
            a, b = cut
        self.drawn.append(pyglet.shapes.Line(
            a[0], a[1], b[0], b[1], thickness=thick, color=colour,
            batch=self.batch, group=group))

    def disc(self, p, r, colour, group) -> None:
        if p is None:
            return
        if self.clip is not None:
            x0, y0, x1, y1 = self.clip
            if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1):
                return
            r = min(r, p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1]) \
                if r > 4 else r
        self.drawn.append(pyglet.shapes.Circle(
            p[0], p[1], max(0.5, r), color=colour, batch=self.batch,
            group=group))

    def poly(self, points: Sequence[Optional[Tuple[float, float]]], colour,
             group) -> None:
        pts = [(q[0], q[1]) for q in points if q is not None]
        if len(pts) != len(points):
            return
        if self.clip is not None:
            pts = self._cut_poly(pts)
        if len(pts) >= 3:
            self.drawn.append(pyglet.shapes.Polygon(
                *pts, color=colour, batch=self.batch, group=group))

    def _cut_poly(self, pts):
        """*pts* cut to the scene's rectangle (Sutherland-Hodgman)."""
        x0, y0, x1, y1 = self.clip
        for inside, cross in (
                (lambda p: p[0] >= x0,
                 lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) /
                               (b[0] - a[0]))),
                (lambda p: p[0] <= x1,
                 lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) /
                               (b[0] - a[0]))),
                (lambda p: p[1] >= y0,
                 lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) /
                               (b[1] - a[1]), y0)),
                (lambda p: p[1] <= y1,
                 lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) /
                               (b[1] - a[1]), y1))):
            out = []
            n = len(pts)
            for i in range(n):
                a, b = pts[i - 1], pts[i]
                if inside(b):
                    if not inside(a):
                        out.append(cross(a, b))
                    out.append(b)
                elif inside(a):
                    out.append(cross(a, b))
            pts = out
            if not pts:
                break
        return pts

    def _cut_line(self, a, b):
        """The part of the segment inside the scene's rectangle
        (Liang-Barsky), or None."""
        x0, y0, x1, y1 = self.clip
        dx, dy = b[0] - a[0], b[1] - a[1]
        lo, hi = 0.0, 1.0
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0),
                     (dy, y1 - a[1])):
            if p == 0:
                if q < 0:
                    return None
                continue
            t = q / p
            if p < 0:
                lo = max(lo, t)
            else:
                hi = min(hi, t)
            if lo > hi:
                return None
        return ((a[0] + dx * lo, a[1] + dy * lo),
                (a[0] + dx * hi, a[1] + dy * hi))

    def say(self, text, x, y, size, colour=(235, 238, 250, 255), anchor='center',
            bold=False, group=None) -> None:
        self._text(text, x, y, size, anchor=anchor, bold=bold, colour=colour,
                   group=group or pyglet.graphics.Group(order=300))

    # --- 3D, clipped at the lens -------------------------------------------------

    @staticmethod
    def _clip(lens, pts, near: float = 0.08):
        """*pts* (a polygon in the world) cut where it passes behind the
        lens, as screen points; empty if none of it is in front."""
        ex, ey, ez = lens.eye
        f = lens.f
        depth = [(p[0] - ex) * f[0] + (p[1] - ey) * f[1] + (p[2] - ez) * f[2]
                 for p in pts]
        out = []
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            da, db = depth[i], depth[(i + 1) % n]
            if da >= near:
                out.append(a)
            if (da >= near) != (db >= near):
                s = (near - da) / (db - da)
                out.append(tuple(a[j] + (b[j] - a[j]) * s for j in range(3)))
        seen = [lens.see(p, near * 0.5) for p in out]
        return [(q[0], q[1]) for q in seen if q is not None]

    def face(self, lens, pts, colour, group) -> None:
        """A flat polygon in the world."""
        self.poly(self._clip(lens, pts), colour, group)

    def seg(self, lens, a, b, thick, colour, group) -> None:
        """A line in the world."""
        q = self._clip(lens, [a, b, b])
        if len(q) >= 2:
            self.line(q[0], q[-1], thick, colour, group)

    def ball(self, lens, p, r, colour, group, shade: float = 0.25) -> None:
        """A sphere of radius *r* at *p*."""
        q = lens.see(p)
        if q is None:
            return
        rr = lens.size(r, q[2])
        self.disc(q, rr, tuple(int(c * (1 - shade)) for c in colour[:3]),
                  group)
        self.disc((q[0] - rr * 0.15, q[1] + rr * 0.15), rr * 0.8, colour,
                  group)

    def box(self, lens, x0, y0, z0, x1, y1, z1, colour, group) -> None:
        """A box's faces that turn toward the lens, shaded by side."""
        ex, ey, ez = lens.eye
        faces = []
        if ex < x0:
            faces.append(([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1),
                           (x0, y0, z1)], 0.75))
        if ex > x1:
            faces.append(([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1),
                           (x1, y1, z0)], 0.75))
        if ez < z0:
            faces.append(([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0),
                           (x0, y1, z0)], 0.9))
        if ez > z1:
            faces.append(([(x0, y0, z1), (x0, y1, z1), (x1, y1, z1),
                           (x1, y0, z1)], 0.9))
        if ey > y1:
            faces.append(([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1),
                           (x0, y1, z1)], 1.0))
        if ey < y0:
            faces.append(([(x0, y0, z0), (x0, y0, z1), (x1, y0, z1),
                           (x1, y0, z0)], 0.6))
        for pts, k in faces:
            self.face(lens, pts, tuple(int(c * k) for c in colour[:3]) +
                      tuple(colour[3:]), group)

    @staticmethod
    def camera(eye, look, left, bottom, width, height, fov: float = 70.0,
               x_right: bool = False):
        """A lens at *eye* looking along *look*, filling the rectangle,
        *fov* degrees across. *x_right*: see :class:`Lens`."""
        import math
        from .lens import Lens
        focal = width / (2 * math.tan(math.radians(fov) / 2))
        target = (eye[0] + look[0], eye[1] + look[1], eye[2] + look[2])
        up = (0.0, 1.0, 0.0)
        if abs(look[1]) > 0.999 * math.sqrt(sum(c * c for c in look)):
            up = (0.0, 0.0, 1.0)
        return Lens(eye, target, focal, left + width / 2, bottom + height / 2,
                    up=up, x_right=x_right)
