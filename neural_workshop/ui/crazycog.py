# -*- coding: utf-8 -*-
"""Crazy Cog on screen: a workshop board, a motor, a winch, and a tray
of cogs.

The board is a pegboard on the workshop wall. The motor sits on the
left with a clockwise arrow on its case; the winch has a rope over its
drum and a bucket on the end, with a flag at the height it has to
reach; from the middle rungs a fan wants turning the way its arrow
shows, and later at a speed its dial marks in green. Every cog turns as
the train turns it, teeth and all. A cog in the hand shows a ghost of
where it will land, green if it fits and red if it does not.

Every cog in the tray is marked with its teeth, and hovering over one
shows it at its true size just above the tray. Chains run between two
cogs as a belt with its links moving.

From rung 10 the machine is a box with depth: up to five glass planes,
one behind the other, the motor on the front one and the winch on the
deepest. The plane in hand is drawn full size where the board is; the
planes behind it shrink toward a vanishing point at the back, each
dimmer than the last, and the planes in front of it are ghosts, so the
whole train can be seen in depth. Shafts run back through the planes
from a cog to the cog on the same axle behind it, with a brass hub on
each. The scene swings a little toward the plane in hand.

Mouse: drag a cog from the tray onto the board; drag a placed cog to
move it or back to the tray; drag the chain onto one cog, then click
the cog it runs to.
Keys: R clears the board; Tab (or F) goes a plane deeper, G (or
Shift+Tab) a plane nearer; 1-5 jump straight to a plane.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 clears the board; 15 goes a plane deeper
(from the back, round to the front) and 16 a plane nearer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import crazycog as model
from ..i18n import _
from . import polish
from .handtask import HandTask

METALS = {22.0: (214, 170, 70), 30.0: (190, 196, 206), 40.0: (196, 110, 70),
          52.0: (150, 160, 120), 66.0: (120, 130, 160)}


class CrazyCog(HandTask):
    """A train of cogs from the motor to the winch."""

    instance: Optional['CrazyCog'] = None

    TITLE = 'Crazy Cog'
    TASK_ID = 'crazy_cog'
    PREFIX = 'COG'
    CATEGORY = 'reasoning'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.R: model.CLEAR, key.TAB: model.LAYER,
                  key.F: model.LAYER, key.G: model.NEARER}
    BACK = (66, 50, 40)
    FOOTNOTE = _('Drag cogs and chains from the tray   Tab/G: deeper or '
                 'nearer plane   R: clear   Esc: menu')
    #: Where the planes recede to, and how much smaller each plane back.
    VANISH = (640.0, 470.0)
    SHRINK = 0.84

    def on_key_press(self, symbol, modifiers):
        run = self.run
        if run is not None and self.phase == self.PLAY:
            if symbol == key.TAB and modifiers & key.MOD_SHIFT:
                model.act(run, model.NEARER)
                return True
            if key._1 <= symbol <= key._5:
                want = symbol - key._1
                if want < run.level.layers:
                    while run.layer != want:
                        model.act(run, model.LAYER)
                return True
        return super().on_key_press(symbol, modifiers)

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Gear the motor to the winch: lift the bucket')
        if self.run is not None and self.run.level.layers > 1:
            self.message = _('The winch is on plane %d, at the back: '
                             'carry the drive there on shared axles') % (
                                 self.run.level.layers)
        if self.run is not None and self.run.machine.fan is not None:
            self.message = _('Lift the bucket, and turn the fan its way')
        return ok

    # --- pieces --------------------------------------------------------

    def cog(self, x, y, r, turn, colour, group, ghost=None, alpha=255,
            teeth=None) -> None:
        n = teeth or model.teeth(r)
        depth = min(7.0, r * 0.22)
        body = r - depth
        if ghost is not None:
            colour = rim = ghost
        else:
            rim = polish.mix(colour, (0, 0, 0), 0.35) + (alpha,)
            colour = tuple(colour[:3]) + (alpha,)
        for k in range(n):
            a = turn + 2 * math.pi * k / n
            h = math.pi / n * 0.5
            self.poly([(x + (body - 1) * math.cos(a - h * 1.3),
                        y + (body - 1) * math.sin(a - h * 1.3)),
                       (x + r * math.cos(a - h * 0.7),
                        y + r * math.sin(a - h * 0.7)),
                       (x + r * math.cos(a + h * 0.7),
                        y + r * math.sin(a + h * 0.7)),
                       (x + (body - 1) * math.cos(a + h * 1.3),
                        y + (body - 1) * math.sin(a + h * 1.3))],
                      rim, group)
        self.disc((x, y), body, rim, group)
        self.disc((x, y), body - 2.5, colour, group)
        if ghost is not None:
            return
        self.disc((x - body * 0.15, y + body * 0.15), body * 0.75,
                  polish.lighter(colour, 0.15) + (alpha,), group)
        if r >= 30:                              # holes in the web
            for k in range(5 if r >= 52 else 4):
                a = turn + 2 * math.pi * k / (5 if r >= 52 else 4)
                self.disc((x + body * 0.55 * math.cos(a),
                           y + body * 0.55 * math.sin(a)), body * 0.18,
                          polish.mix(colour, (0, 0, 0), 0.6) + (alpha,),
                          group)
        self.disc((x, y), max(5.0, r * 0.2), rim, group)
        self.disc((x, y), 3.0, (30, 30, 30, alpha), group)
        self.line((x, y), (x + max(5.0, r * 0.2) * math.cos(turn),
                           y + max(5.0, r * 0.2) * math.sin(turn)), 2,
                  (240, 240, 240, alpha), group)

    def chain(self, run, a, b, alpha=255, group=None,
              turn=None) -> None:
        """A chain round two cogs: the two straight runs, links moving
        along them as the cogs turn."""
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        if d <= abs(a.r - b.r):
            return
        th = math.atan2(dy, dx)
        beta = math.acos((a.r - b.r) / d)
        move = run.angle.get(a, 0.0) * a.r if turn is None else turn
        for side in (-1, 1):
            ang = th + side * beta
            pa = (a.x + a.r * math.cos(ang), a.y + a.r * math.sin(ang))
            pb = (b.x + b.r * math.cos(ang), b.y + b.r * math.sin(ang))
            self.line(pa, pb, 5, (40, 36, 34, alpha), group)
            span = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1.0
            k = (move * side) % 14.0
            while k < span:
                t = k / span
                self.disc((pa[0] + (pb[0] - pa[0]) * t,
                           pa[1] + (pb[1] - pa[1]) * t), 2.2,
                          (150, 150, 160, alpha), group)
                k += 14.0
        for c in (a, b):                        # round the cogs
            self.disc((c.x, c.y), c.r + 1.5, (40, 36, 34, int(alpha * 0.35)),
                      group)

    def arrow(self, x, y, rad, way, colour, group) -> None:
        """A curved arrow round (x, y), anticlockwise for way 1."""
        pts = []
        for k in range(10):
            a = math.pi * 0.25 + way * (k / 9.0) * math.pi * 1.2
            pts.append((x + rad * math.cos(a), y + rad * math.sin(a)))
        for a, b in zip(pts, pts[1:]):
            self.line(a, b, 3, colour, group)
        end = math.pi * 0.25 + way * math.pi * 1.2
        ex, ey = x + rad * math.cos(end), y + rad * math.sin(end)
        tx, ty = -math.sin(end) * way, math.cos(end) * way
        self.poly([(ex + tx * 9, ey + ty * 9),
                   (ex - tx * 3 + math.cos(end) * 6,
                    ey - ty * 3 + math.sin(end) * 6),
                   (ex - tx * 3 - math.cos(end) * 6,
                    ey - ty * 3 - math.sin(end) * 6)], colour, group)

    # --- the scene -----------------------------------------------------

    def _scene(self, run, s: float) -> None:
        mc = run.machine
        l, b, rt, t = model.BOARD
        g = self.g()
        n = run.level.layers
        if n == 1:
            self.rect(l, b, rt - l, t - b, (196, 164, 120), g)  # pegboard
            for gx in range(int(l) + 20, int(rt), 40):
                for gy in range(int(b) + 20, int(t), 40):
                    self.disc((gx, gy), 2.5, (150, 120, 86), g)
        else:
            # A box seen into: the pegboard is its back wall, behind the
            # deepest plane; dark sides lead back to it.
            self.rect(l, b, rt - l, t - b, (58, 46, 38), g)
            k, ox, oy = self.depth(run, n)
            self.rect(ox + l * k, oy + b * k, (rt - l) * k, (t - b) * k,
                      (150, 124, 92), g)
            for gx in range(int(l) + 20, int(rt), 40):
                for gy in range(int(b) + 20, int(t), 40):
                    self.disc((ox + gx * k, oy + gy * k), 2.0 * k,
                              (115, 92, 66), g)
        self.rect(0, 0, 1000, b - 6, (52, 40, 32), g)           # the tray
        self.rect(0, b - 8, 1000, 4, (30, 24, 20), g)
        if run.level.layers > 1:                 # the box's floor and sides
            n = run.level.layers - 1
            for corner in ((l, b), (rt, b), (l, t), (rt, t)):
                self.line(self.at(run, corner[0], corner[1], 0),
                          self.at(run, corner[0], corner[1], n), 1,
                          (90, 70, 50, 160), g)
        # The winch on its plane: the bucket, its rope and the flag.
        wz = mc.winch_z
        k, _ox, _oy = self.depth(run, wz)
        al = self.fade(run, wz) if wz != run.layer else 255

        def T(x, y, z=wz):
            return self.at(run, x, y, z)
        g = self.g()
        wx, wy = mc.winch
        rope_x = wx + model.DRUM
        top_y = model.FLOOR + mc.lift
        bucket_y = model.FLOOR + run.height
        self.poly([T(rope_x - 24, model.FLOOR - 4), T(rope_x + 24,
                   model.FLOOR - 4), T(rope_x + 24, model.FLOOR),
                   T(rope_x - 24, model.FLOOR)], (90, 70, 50, al), g)
        self.line(T(rope_x + 4, top_y + 26), T(rope_x + 70, top_y + 26), 2,
                  (60, 140, 70, al), g)
        self.poly([T(rope_x + 70, top_y + 26), T(rope_x + 70, top_y + 46),
                   T(rope_x + 90, top_y + 38)], (80, 190, 90, al), g)
        self.line(T(rope_x, wy), T(rope_x, bucket_y + 30), 2,
                  (90, 70, 40, al), g)
        self.line(T(rope_x - 14, bucket_y + 22), T(rope_x, bucket_y + 30), 2,
                  (60, 60, 60, al), g)
        self.line(T(rope_x + 14, bucket_y + 22), T(rope_x, bucket_y + 30), 2,
                  (60, 60, 60, al), g)
        self.poly([T(rope_x - 16, bucket_y + 22), T(rope_x + 16, bucket_y + 22),
                   T(rope_x + 12, bucket_y), T(rope_x - 12, bucket_y)],
                  (110, 120, 140, al), g)
        if run.level.load > 0.5:
            self.words('%.1f' % run.level.load, *T(rope_x, bucket_y + 8),
                       9 * max(0.7, k), colour=(255, 255, 255, 230), group=g)
        # The motor's case on the front plane, the drum, the fan.
        g = self.g()
        mx, my = mc.motor
        km, _a, _b = self.depth(run, 0)
        am = self.fade(run, 0) if run.layer else 255
        cx, cy = self.at(run, mx, my, 0)
        self.rect(cx - 46 * km, cy - 46 * km, 92 * km, 92 * km,
                  (60, 70, 90, am), g)
        self.rect(cx - 42 * km, cy - 42 * km, 84 * km, 84 * km,
                  (80, 92, 116, am), g)
        if run.layer == 0:
            self.words(_('MOTOR'), cx, cy - 60 * km, 10, bold=True,
                       colour=(230, 220, 200, 255) if run.level.layers > 1
                       else (40, 40, 50, 255), group=g)
        dx, dy = T(wx, wy)
        self.disc((dx, dy), (model.DRUM + 4) * k, (90, 70, 50, al), g)
        self.disc((dx, dy), model.DRUM * k, (150, 120, 80, al), g)
        if wz >= run.layer:
            self.words(_('WINCH') + ('' if run.level.layers == 1 else
                                     ' (%d)' % (wz + 1)),
                       dx, dy + 84 * k, 10 * max(0.75, k), bold=True,
                       colour=(230, 220, 200, 255) if run.level.layers > 1
                       else (40, 40, 50, 255), group=g)
        if mc.fan is not None:
            fz = mc.fan_z
            kf, _a, _b = self.depth(run, fz)
            af = self.fade(run, fz) if fz != run.layer else 255
            fx, fy = self.at(run, mc.fan[0], mc.fan[1], fz)
            f = run.on(mc.fan, fz)
            spin = run.angle.get(f, 0.0) if f is not None else 0.0
            for i_ in range(3):
                a = spin * 1.0 + 2 * math.pi * i_ / 3
                self.poly([(fx, fy), (fx + 50 * kf * math.cos(a - 0.3),
                                      fy + 50 * kf * math.sin(a - 0.3)),
                           (fx + 56 * kf * math.cos(a + 0.1),
                            fy + 56 * kf * math.sin(a + 0.1))],
                          (180, 210, 230, af), g)
            self.arrow(fx, fy, 66 * kf, mc.fan_way, (40, 120, 200, af), g)
            if fz >= run.layer:
                self.words(_('FAN') + ('' if run.level.layers == 1 else
                                       ' (%d)' % (fz + 1)),
                           fx, fy + 80 * kf, 10 * max(0.75, kf), bold=True,
                           colour=(230, 220, 200, 255)
                           if run.level.layers > 1 else (40, 40, 50, 255),
                           group=g)
        self.arrow(cx, cy, 34 * km, -1, (240, 200, 70, am), g)
        for p, pz in zip(run.pegs, run.peg_z):                  # axles
            if run.on(p, pz) is None:
                kp, _a, _b = self.depth(run, pz)
                q = self.at(run, p[0], p[1], pz)
                ap = 255 if pz == run.layer else self.fade(run, pz)
                self.disc(q, 8 * kp, (60, 50, 40, ap), g)
                self.disc(q, 5 * kp, (200, 180, 120, ap), g)
        self._layers(run)
        self._tray(run)
        # The cog in the hand, and a ghost of where it will land.
        if run.carry is not None and run.carry != model.CHAIN:
            g = self.g()
            hx, hy = run.hand.x, run.hand.y
            if hy >= model.BOARD[1]:
                c = run.snap(hx, hy, run.carry)
                self.cog(c.x, c.y, c.r, 0.0, None, g,
                         ghost=(90, 220, 110, 110) if run.placeable(c)
                         else (230, 70, 60, 110))
            self.cog(hx, hy, run.carry, 0.0,
                     METALS.get(run.carry, (180, 180, 180)), self.g())
        elif run.carry == model.CHAIN:
            self._coil(run.hand.x, run.hand.y, self.g())
        if run.chain_from is not None:
            a = run.chain_from
            self.line((a.x, a.y), (run.hand.x, run.hand.y), 5,
                      (40, 36, 34, 220), self.g())
        # Words over it all.
        hud = pyglet.graphics.Group(order=900)
        gear = run.gearing()
        if run.jammed:
            self.words(_('JAMMED'), 500, 612, 16, bold=True, group=hud,
                       colour=(255, 110, 90, 255))
        elif gear is not None and gear > 0 and \
                model.lift_speed(1.0 / gear, run.level.load) <= 0.0:
            self.words(_('STALLED: gear it down'), 500, 612, 14, bold=True,
                       group=hud, colour=(255, 170, 80, 255))
        elif gear is not None and gear < 0:
            self.words(_('The winch turns the wrong way'), 500, 612, 14,
                       bold=True, group=hud, colour=(255, 170, 80, 255))
        if mc.fan is not None and run.level.fan >= 2:
            self.dial(run, hud)

    # --- depth ---------------------------------------------------------

    def depth(self, run, z: int):
        """How plane *z* is drawn: (scale, shift x, shift y), the plane in
        hand at full size where the board is."""
        d = z - run.layer
        # Behind: smaller toward the vanishing point. In front: only a
        # little larger, so a ghost of the near planes stays in the frame.
        k = self.SHRINK ** d if d >= 0 else 1.0 - 0.05 * d
        vx, vy = self.VANISH
        return k, vx * (1 - k), vy * (1 - k)

    def at(self, run, x: float, y: float, z: int):
        k, ox, oy = self.depth(run, z)
        return ox + x * k, oy + y * k

    def seen(self, run, c):
        """A cog as drawn on its plane."""
        k, ox, oy = self.depth(run, c.z)
        return model.Cog(ox + c.x * k, oy + c.y * k, c.r * k, c.z)

    def fade(self, run, z: int) -> int:
        d = z - run.layer
        if d == 0 or run.level.layers == 1:
            return 255
        return 40 if d < 0 else max(80, 200 - 40 * d)

    def _plane(self, run, z: int) -> None:
        """A glass plane: its edge and a faint pane, its walls."""
        mc = run.machine
        l, b, rt, t = model.BOARD
        k, ox, oy = self.depth(run, z)
        alpha = self.fade(run, z)
        g = self.g()
        if run.level.layers > 1 and z != run.layer:
            x0, y0 = ox + l * k, oy + b * k
            w, h = (rt - l) * k, (t - b) * k
            self.rect(x0, y0, w, h, (150, 190, 220, alpha // 6), g)
            edge = (200, 230, 255, min(255, alpha + 40))
            for p, q in (((x0, y0), (x0 + w, y0)), ((x0, y0 + h),
                         (x0 + w, y0 + h)), ((x0, y0), (x0, y0 + h)),
                         ((x0 + w, y0), (x0 + w, y0 + h))):
                self.line(p, q, 1.5, edge, g)
            if z > run.layer:                    # its number, at the edge
                self.words(str(z + 1), x0 + 10, y0 + h - 10, 9, bold=True,
                           colour=(230, 240, 255, alpha), group=g)
        for w in mc.walls:
            if w[4] != z:
                continue
            wx, wy, ww, wh = w[:4]
            px, py = ox + wx * k, oy + wy * k
            base = (90, 94, 104) if z == 0 else (80, 70, 62)
            self.rect(px, py, ww * k, wh * k, base + (alpha,), g)
            self.rect(px + 3 * k, py + 3 * k, (ww - 6) * k, (wh - 6) * k,
                      polish.lighter(base, 0.2) + (alpha,), g)

    def _shafts(self, run) -> None:
        """Steel shafts from each cog back to the cog on its axle behind,
        and from the motor, winch and fan cases to their planes."""
        g = self.g()
        cogs = run.cogs
        for a in cogs:
            for b in cogs:
                if b.z > a.z and model.same_axle(a, b):
                    pa = self.at(run, a.x, a.y, a.z)
                    pb = self.at(run, b.x, b.y, b.z)
                    al = max(self.fade(run, a.z), self.fade(run, b.z))
                    self.line(pa, pb, 6, (60, 64, 72, al), g)
                    self.line(pa, pb, 3, (190, 196, 210, al), g)

    def _layers(self, run) -> None:
        """Back to front: each plane, its walls, cogs and chains; shafts
        between them; the plane in hand last but for the ones in front."""
        n = run.level.layers
        order = sorted(range(n), key=lambda z: (-(z >= run.layer), -z, z))
        behind = [z for z in order if z > run.layer]
        front = [z for z in range(n) if z < run.layer]
        for z in behind + [run.layer] + sorted(front, reverse=True):
            if z == run.layer:
                self._shafts(run)
            self._plane(run, z)
            alpha = self.fade(run, z)
            g = self.g()
            if n > 1 and z == run.layer:         # shadows on the plane behind
                for c in run.cogs:
                    if c.z == z:
                        sc = self.seen(run, c)
                        self.disc((sc.x + 6, sc.y - 6), sc.r,
                                  (0, 0, 0, 40), g)
            for c in run.cogs:
                if c.z != z:
                    continue
                sc = self.seen(run, c)
                colour = METALS.get(c.r, (180, 180, 180))
                if z > run.layer:
                    colour = polish.mix(colour, (40, 50, 70),
                                        0.15 * (z - run.layer))
                self.cog(sc.x, sc.y, sc.r, run.angle.get(c, 0.0), colour, g,
                         alpha=alpha)
                if any(model.same_axle(c, o) for o in run.cogs):
                    self.disc((sc.x, sc.y), 9 * sc.r / c.r,
                              (230, 200, 90, alpha), g)
                    self.disc((sc.x, sc.y), 4 * sc.r / c.r,
                              (60, 50, 30, alpha), g)
            g = self.g()
            for a, b in run.chains:
                if a.z == z:
                    self.chain(run, self.seen(run, a), self.seen(run, b),
                               alpha, g, turn=run.angle.get(a, 0.0) * a.r)
        if n > 1:
            hud = pyglet.graphics.Group(order=890)
            for z in range(n):
                on = z == run.layer
                x0 = 36 + 46 * z
                w = 40
                self.rect(x0, 600, w, 22, ((240, 200, 70) if on
                                           else (90, 80, 70)), hud)
                self.words(str(z + 1), x0 + w / 2, 611, 10, bold=True,
                           group=hud,
                           colour=(30, 26, 20, 255) if on
                           else (200, 190, 180, 255))
            self.words(_('plane %d of %d   Tab: deeper   G: nearer') % (
                run.layer + 1, n), 46 + 46 * n, 611, 9, group=hud,
                anchor='left', colour=(255, 255, 255, 220))

    def _coil(self, x, y, group, n: Optional[int] = None) -> None:
        for k in range(3):
            self.oval((x, y - 6 + 6 * k), 20, 8, (40, 36, 34), group)
            self.oval((x, y - 6 + 6 * k), 15, 4, (90, 84, 80), group)
        if n is not None:
            self.words('x%d' % n, x + 26, y - 14, 10, bold=True,
                       group=group, colour=(240, 230, 210, 255))

    def _tray(self, run) -> None:
        g = self.g()
        n = run.slots()
        k_ = 0.66 if model.gap(n) >= 95 else 0.5
        hover = None
        for k in range(n):
            sx, sy = model.slot(k, n)
            self.disc((sx, sy), min(44.0, model.gap(n) / 2 - 4),
                      (66, 52, 42), g)
            if k == run.chain_slot():
                if run.chain_stock > 0:
                    self._coil(sx, sy + 4, g, run.chain_stock)
                self.words(_('chain'), sx, sy + 40, 9, group=g,
                           colour=(230, 220, 200, 230))
                continue
            r = run.tray[k]
            if r is None:
                continue
            self.cog(sx, sy, r * k_, 0.0, METALS.get(r, (180, 180, 180)),
                     g, teeth=model.teeth(r))
            self.words(_('%d teeth') % model.teeth(r), sx, sy + 40, 9,
                       group=g, colour=(230, 220, 200, 230))
            if run.carry is None and run.chain_from is None and \
                    abs(run.hand.x - sx) <= model.gap(n) / 2 and \
                    abs(run.hand.y - sy) <= 40:
                hover = (sx, r)
        if hover is not None:                    # its true size, above
            sx, r = hover
            sx = max(model.BOARD[0] + r, min(model.BOARD[2] - r, sx))
            self.cog(sx, model.BOARD[1] + r + 4, r, 0.0, None, self.g(),
                     ghost=(255, 255, 255, 90))

    def dial(self, run, group) -> None:
        mc = run.machine
        cx, cy = 900.0, 612.0
        top = mc.fan_band[1] * 2.0
        self.rect(cx - 70, cy - 12, 140, 22, (30, 30, 36), group)
        lo, hi = (mc.fan_band[0] / top, mc.fan_band[1] / top)
        self.rect(cx - 66 + 132 * lo, cy - 8, 132 * (hi - lo), 14,
                  (80, 190, 90), group)
        at = max(0.0, min(1.0, abs(run.fan_speed()) / top))
        self.rect(cx - 66 + 132 * at - 1.5, cy - 10, 3, 18,
                  (255, 255, 255), group)
        self.words(_('fan speed'), cx - 110, cy - 4, 9, group=group,
                   colour=(255, 255, 255, 220))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
