# -*- coding: utf-8 -*-
"""Drone Hoops on screen: a walled yard at dusk, seen through whichever
camera the rung is using.

A checkered yard with low walls and tall corner posts, hoops on poles,
and the drone: an orange body with four rotors that tilt the way it is
thrusting, a green light at the nose and a red one at the tail, a
shadow on the ground under it and a thin line down to the shadow, so
its height reads at a glance. The next hoop glows gold on the first
rungs. Fixed cameras show their number in the corner, the way a
security monitor does. Wind shows as streaks only once a gust is
blowing -- it is heard before that -- and lightning whitens the whole
picture.

Mouse: hold the left button and the drone flies to the spot under the
pointer, at its own height; the wheel raises and lowers that height.
Keys: arrows / WASD push across the screen, Space / E up, Shift / Q
down. Keys take over from the mouse until it is pressed again.

For the agent boundary: ports 0-7 push forward, back, left, right and
the four diagonals relative to the camera, for the step they are sent
in; 8 and 9 push up and down. The agent hears everything the player
hears.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import dronehoops as model
from .. import state
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .lens import Lens
from .pointer import Pointer
from .tones import Tones, patch

GOLD = (255, 200, 60)
STEEL = (190, 198, 214)
DONE = (120, 220, 140)
BODY = (240, 130, 40)
SKY_LOW, SKY_HIGH = (238, 160, 120), (46, 52, 104)
TILE_A, TILE_B = (118, 132, 104), (98, 112, 90)
WALL = (150, 120, 96)
Pt = Tuple[float, float]


def clip_line(a: Pt, b: Pt, box: Sequence[float]
              ) -> Optional[Tuple[Pt, Pt]]:
    """The part of segment a-b inside box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0),
                 (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            lo = max(lo, r)
        else:
            hi = min(hi, r)
        if lo > hi:
            return None
    return ((a[0] + lo * dx, a[1] + lo * dy), (a[0] + hi * dx, a[1] + hi * dy))


def clip_poly(points: List[Pt], box: Sequence[float]) -> List[Pt]:
    """A convex polygon cut down to box (Sutherland-Hodgman)."""
    x0, y0, x1, y1 = box
    edges = ((lambda p: p[0] >= x0, lambda a, b: _at_x(a, b, x0)),
             (lambda p: p[0] <= x1, lambda a, b: _at_x(a, b, x1)),
             (lambda p: p[1] >= y0, lambda a, b: _at_y(a, b, y0)),
             (lambda p: p[1] <= y1, lambda a, b: _at_y(a, b, y1)))
    out = points
    for inside, cut in edges:
        if not out:
            break
        src, out = out, []
        for k, cur in enumerate(src):
            prev = src[k - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(cut(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cut(prev, cur))
    return out


def _at_x(a: Pt, b: Pt, x: float) -> Pt:
    u = (x - a[0]) / ((b[0] - a[0]) or 1e-9)
    return (x, a[1] + u * (b[1] - a[1]))


def _at_y(a: Pt, b: Pt, y: float) -> Pt:
    u = (y - a[1]) / ((b[1] - a[1]) or 1e-9)
    return (a[0] + u * (b[0] - a[0]), y)


class DroneHoops(Pointer, Tones, ClockedTask):
    """Fly through every hoop, in order."""

    instance: Optional['DroneHoops'] = None

    TITLE = 'Drone Hoops'
    TASK_ID = 'drone_hoops'
    PREFIX = 'DRONE'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    FOOTNOTE = _('Hold mouse: fly to pointer, wheel: height   '
                 'Arrows / WASD: move   Space: up   Shift: down   Esc: menu')

    def __init__(self) -> None:
        self.lens: Optional[Lens] = None
        self.box = (0.0, 0.0, 1.0, 1.0)
        super().__init__()
        state.window.push_handlers(self.on_mouse_scroll)

    def close(self) -> None:
        if type(self).instance is self:
            try:
                state.window.remove_handlers(self.on_mouse_scroll)
            except Exception:
                pass
        super().close()

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        self.message = (_('Fly through the gold hoop, then the next')
                        if run.level.lit else
                        _('Follow the bell: fly through the hoop that rings'))
        self._tones_live(run.notes, [patch(n, k + 1) for k, n in
                                     enumerate(model.PATCHES)],
                         run.end + 2.0)
        return ok

    # --- controls ---------------------------------------------------------------

    def _held(self):
        k = self.keys
        on = set()
        if k[key.UP] or k[key.W]:
            on.add(model.FORWARD)
        if k[key.DOWN] or k[key.S]:
            on.add(model.BACK)
        if k[key.LEFT] or k[key.A]:
            on.add(model.LEFT)
        if k[key.RIGHT] or k[key.D]:
            on.add(model.RIGHT)
        if k[key.SPACE] or k[key.E]:
            on.add(model.UP)
        if k[key.LSHIFT] or k[key.RSHIFT] or k[key.Q]:
            on.add(model.DOWN)
        return on or None

    def _aim_at(self, x: float, y: float) -> None:
        run = self.run
        if run is None or self.lens is None or self.phase != self.PLAY:
            return
        spot = self.lens.on_floor(x, y, y=run.p[1])
        if spot is None:
            return
        lim = model.HALF - 0.5
        run.aim = (max(-lim, min(lim, spot[0])), max(-lim, min(lim, spot[1])))
        if run.aim_y is None:
            run.aim_y = run.p[1]

    def _click(self, x: float, y: float, button: int) -> None:
        if button == mouse.LEFT and self.run is not None and \
                self.phase == self.PLAY:
            self._aim_at(x, y)
            return
        super()._click(x, y, button)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        run = self.run
        if run is None or self.phase != self.PLAY:
            return
        base = run.aim_y if run.aim_y is not None else run.p[1]
        run.aim_y = max(model.FLOOR, min(model.CEILING,
                                         base + 0.5 * scroll_y))
        if run.aim is None:
            run.aim = (run.p[0], run.p[2])

    def _tick(self) -> None:
        if self.run is not None and self.pointer and \
                self.buttons & mouse.LEFT:
            self._aim_at(*self.pointer)
        super()._tick()

    # --- drawing ------------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        d, batch = self.drawn, self.batch
        eye, look, cam = run.camera()
        focal = height * 0.95
        if cam >= 0:
            # A fixed camera zooms to keep the drone a steady size.
            far = model.norm(model.sub(run.p, eye))
            focal *= max(1.0, min(2.6, far / 11.0))
        lens = self.lens = Lens(eye, look, focal, left + width / 2,
                                bottom + height / 2)
        box = self.box = (left, bottom, left + width, bottom + height)
        flash = run.flash()
        g_sky = pyglet.graphics.Group(order=-14)
        g_floor = pyglet.graphics.Group(order=-12)
        g_mark = pyglet.graphics.Group(order=-11)
        polish.card(d, batch, left - 4, bottom - 4, width + 8, height + 8,
                    (30, 30, 50), radius=14, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        lit = lambda c: polish.mix(c, (255, 255, 255), flash * 0.6)  # noqa
        polish.gradient(d, batch, left, bottom, width, height,
                        lit(SKY_LOW), lit(SKY_HIGH), bands=18, group=g_sky)
        # The land beyond the yard, up to the horizon.
        ahead = model.unit((look[0] - eye[0], 0.0, look[2] - eye[2]))
        rim = lens.see(model.add(eye, model.scale(ahead, 1e4)))
        if rim is not None and rim[1] > bottom:
            top = min(bottom + height, rim[1])
            d.append(pyglet.shapes.Rectangle(
                left, bottom, width, top - bottom, color=lit((112, 102, 118)),
                batch=batch, group=pyglet.graphics.Group(order=-13)))

        def flat(p) -> Optional[Pt]:
            q = lens.see(p)
            return (q[0], q[1]) if q else None

        def poly(points, colour, group) -> None:
            if any(p is None for p in points):
                return
            pts = clip_poly(list(points), box)
            if len(pts) >= 3:
                d.append(pyglet.shapes.Polygon(*pts, color=colour,
                                               batch=batch, group=group))

        def line(a, b, thick, colour, group) -> None:
            pa, pb = lens.see(a), lens.see(b)
            if pa is None or pb is None:
                return
            seg = clip_line(pa[:2], pb[:2], box)
            if seg:
                d.append(pyglet.shapes.Line(*seg[0], *seg[1],
                                            thickness=thick, color=colour,
                                            batch=batch, group=group))

        # The yard: tiles, walls, posts.
        H = model.HALF
        n = 12
        step = 2 * H / n
        for i in range(n):
            for j in range(n):
                x0, z0 = -H + i * step, -H + j * step
                c = TILE_A if (i + j) % 2 else TILE_B
                poly([flat((x0, 0, z0)), flat((x0 + step, 0, z0)),
                      flat((x0 + step, 0, z0 + step)),
                      flat((x0, 0, z0 + step))], lit(c), g_floor)
        corners = [(-H, -H), (H, -H), (H, H), (-H, H)]
        for k in range(4):
            (ax, az), (bx, bz) = corners[k], corners[(k + 1) % 4]
            poly([flat((ax, 0, az)), flat((bx, 0, bz)), flat((bx, 1.0, bz)),
                  flat((ax, 1.0, az))], lit(WALL) + (200,), g_mark)
            line((ax, 0, az), (ax, model.CEILING, az), 3,
                 (70, 60, 70, 200), g_mark)
            line((ax, model.CEILING, az), (bx, model.CEILING, bz), 1,
                 (255, 255, 255, 50), g_mark)
        # The drone's shadow and height line, on the ground.
        p = run.p
        ring = [flat((p[0] + 0.55 * math.cos(a), 0.02,
                      p[2] + 0.55 * math.sin(a)))
                for a in (2 * math.pi * k / 12 for k in range(12))]
        poly(ring, (20, 20, 30, 120), g_mark)
        line((p[0], 0.02, p[2]), p, 1, (255, 255, 255, 110), g_mark)
        if run.aim is not None:
            ax, az = run.aim
            y = run.aim_y if run.aim_y is not None else p[1]
            for a, b in (((ax - 0.4, y, az), (ax + 0.4, y, az)),
                         ((ax, y, az - 0.4), (ax, y, az + 0.4))):
                line(a, b, 2, (255, 255, 255, 150), g_mark)
        # Everything with depth, far first.
        things: List[Tuple[float, object]] = []
        for k, h in enumerate(run.course.hoops):
            c, nrm = model.hoop_at(h, run.t)
            q = lens.see(c)
            if q is None:
                continue
            for half in (0, 1):
                things.append((q[2] + (0.3 if half == 0 else -0.3),
                               ('hoop', k, half)))
        q = lens.see(p)
        if q is not None:
            things.append((q[2], ('drone',)))
        for k, bird in enumerate(run.course.birds):
            bp = model.bird_at(bird, run.t)
            if bp is not None:
                qb = lens.see(bp)
                if qb is not None:
                    things.append((qb[2], ('bird', k, bp)))
        things.sort(key=lambda it: -it[0])
        for order, (_z, what) in enumerate(things):
            g = pyglet.graphics.Group(order=order)
            if what[0] == 'hoop':
                self._hoop(lens, what[1], what[2], g, line)
            elif what[0] == 'drone':
                self._drone(lens, g, line)
            else:
                self._bird(lens, what[2], g, line)
        g_top = pyglet.graphics.Group(order=180)
        self._wind(lens, g_top, line)
        # Overlays.
        if flash > 0.01:
            d.append(pyglet.shapes.Rectangle(left, bottom, width, height,
                                             color=(255, 255, 255,
                                                    int(200 * flash)),
                                             batch=batch, group=g_top))
        g_hud = pyglet.graphics.Group(order=190)
        if cam >= 0:
            self._text(_('CAM %d') % (cam + 1), left + 52, bottom + height
                       - 24, 13, bold=True, colour=(255, 255, 255, 230))
            if int(run.t * 2) % 2 == 0:
                d.append(pyglet.shapes.Circle(left + 16, bottom + height - 24,
                                              6, color=(230, 40, 40),
                                              batch=batch, group=g_hud))
        elif cam == -1:
            self._text(_('ORBIT'), left + 40, bottom + height - 24, 13,
                       bold=True, colour=(255, 255, 255, 230))
        total = len(run.course.hoops)
        for k in range(total):
            x = left + width - 20 - (total - 1 - k) * 20
            colour = DONE if k < run.next else (255, 255, 255, 90)
            d.append(pyglet.shapes.Circle(x, bottom + height - 22, 6,
                                          color=colour, batch=batch,
                                          group=g_hud))
        share = max(0.0, (run.end - run.t) / run.end)
        if share > 0.005:
            d.append(pyglet.shapes.Rectangle(
                left + 10, bottom + 8, (width - 20) * share, 6,
                color=polish.mix((236, 80, 64), (110, 220, 140),
                                 min(1.0, share * 1.6)),
                batch=batch, group=g_hud))

    def _hoop(self, lens, k, half, g, line) -> None:
        run = self.run
        h = run.course.hoops[k]
        c, n = model.hoop_at(h, run.t)
        u = (n[2], 0.0, -n[0])
        level = run.level
        if k < run.next:
            colour = DONE + (150,)
        elif level.lit and k == run.next:
            colour = GOLD
        else:
            colour = STEEL
        q = lens.see(c)
        if q is None:
            return
        segs = 32
        pts = [model.add(c, (h.radius * (math.cos(a) * u[0]),
                             h.radius * math.sin(a),
                             h.radius * (math.cos(a) * u[2])))
               for a in (2 * math.pi * j / segs for j in range(segs + 1))]
        for j in range(segs):
            a, b = pts[j], pts[j + 1]
            mid = lens.see(model.scale(model.add(a, b), 0.5))
            if mid is None:
                continue
            near = mid[2] < q[2]
            if near != (half == 1):
                continue
            thick = max(2.0, lens.size(2 * model.RIM, mid[2]))
            shade = polish.mix(colour[:3], (255, 255, 255),
                               0.25 if near else 0.0)
            tone = shade + ((colour[3],) if len(colour) > 3 else ())
            line(a, b, thick, tone, g)
            joint = lens.see(b)
            if joint is not None and self._in(joint) and thick > 3 and \
                    len(tone) == 3:
                self.drawn.append(pyglet.shapes.Circle(
                    joint[0], joint[1], thick / 2, color=tone,
                    batch=self.batch, group=g))
        if half == 0:
            line((c[0], c[1] - h.radius, c[2]), (c[0], 0.0, c[2]),
                 max(1.5, lens.size(0.14, q[2])), (90, 80, 90), g)
            if level.lit and k == run.next:
                polish.glow(self.drawn, self.batch, q[0], q[1],
                            lens.size(h.radius * 1.3, q[2]), GOLD,
                            strength=35, group=g)

    def _drone(self, lens, g, line) -> None:
        run = self.run
        p = run.p
        yaw = run.heading
        fwd = (math.sin(yaw), 0.0, math.cos(yaw))
        side = (fwd[2], 0.0, -fwd[0])
        push = run.thrust
        rotors = []
        for a, b in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
            off = model.add(model.scale(fwd, 0.42 * a),
                            model.scale(side, 0.42 * b))
            tilt = -0.18 * model.dot(off, push) / (0.42 * model.ACC)
            rotors.append(model.add(p, (off[0], tilt, off[2])))
        q = lens.see(p)
        if q is None:
            return
        d, batch = self.drawn, self.batch
        for r in rotors:
            line(p, r, max(2.0, lens.size(0.08, q[2])), (60, 60, 70), g)
        for k, r in enumerate(rotors):
            rq = lens.see(r)
            if rq is None or not self._in(rq):
                continue
            size = max(3.0, lens.size(0.24, rq[2]))
            d.append(pyglet.shapes.Circle(rq[0], rq[1], size,
                                          color=(220, 230, 240, 90),
                                          batch=batch, group=g))
            a = run.t * 40 + k
            d.append(pyglet.shapes.Line(rq[0] - math.cos(a) * size,
                                        rq[1] - math.sin(a) * size,
                                        rq[0] + math.cos(a) * size,
                                        rq[1] + math.sin(a) * size,
                                        thickness=2, color=(40, 40, 50),
                                        batch=batch, group=g))
        if self._in(q):
            d.append(pyglet.shapes.Circle(q[0], q[1],
                                          max(3.0, lens.size(0.2, q[2])),
                                          color=BODY, batch=batch, group=g))
        for off, colour in ((0.3, (80, 255, 120)), (-0.3, (255, 70, 60))):
            lq = lens.see(model.add(p, model.scale(fwd, off)))
            if lq is not None and self._in(lq):
                d.append(pyglet.shapes.Circle(lq[0], lq[1],
                                              max(2.0, lens.size(0.08, lq[2])),
                                              color=colour, batch=batch,
                                              group=g))

    def _bird(self, lens, bp, g, line) -> None:
        flap = 0.3 * math.sin(self.run.t * 12 + bp[0])
        for s in (-1, 1):
            line(bp, (bp[0] + 0.5 * s, bp[1] + flap, bp[2] + 0.2), 2,
                 (30, 26, 36), g)

    def _wind(self, lens, g, line) -> None:
        run = self.run
        gust = model.gust_at(run.course, run.t)
        if gust is None:
            return
        w = (math.sin(gust.heading), 0.0, math.cos(gust.heading))
        p = run.p
        for k in range(22):
            a = (k * 7.31) % 1.0
            b = (k * 3.77) % 1.0
            c = (k * 5.13) % 1.0
            along = ((run.t * 14 + k * 3.1) % 14.0) - 7.0
            base = (p[0] + (a - 0.5) * 10 + w[0] * along,
                    max(0.2, p[1] + (b - 0.5) * 5),
                    p[2] + (c - 0.5) * 10 + w[2] * along)
            line(base, model.add(base, model.scale(w, 1.3)), 1.5,
                 (255, 255, 255, 120), g)

    def _in(self, q) -> bool:
        x0, y0, x1, y1 = self.box
        return x0 <= q[0] <= x1 and y0 <= q[1] <= y1

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   hoop %d of %d   bumps %d') % (
            self.rung, self.trial, self.total_trials,
            min(run.next + 1, len(run.course.hoops)),
            len(run.course.hoops), run.bumps)
