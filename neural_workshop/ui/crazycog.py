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
cogs as a belt with its links moving. From rung 13 the board has a
back layer: the one not in hand is drawn faint, the front one casts
shadows on the back, and a cog on the same axle as one on the other
layer shows a brass hub.

Mouse: drag a cog from the tray onto the board; drag a placed cog to
move it or back to the tray; drag the chain onto one cog, then click
the cog it runs to.
Keys: R clears the board; Tab (or F) switches the layer.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 clears the board; 15 switches the
layer.

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
                  key.F: model.LAYER}
    BACK = (66, 50, 40)
    FOOTNOTE = _('Drag cogs and chains from the tray   Tab: front or back '
                 'layer   R: clear   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Gear the motor to the winch: lift the bucket')
        if self.run is not None and self.run.level.layers > 1:
            self.message = _('Gear it to the winch: Tab works on the '
                             'back layer')
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

    def chain(self, run, a, b, alpha=255, group=None) -> None:
        """A chain round two cogs: the two straight runs, links moving
        along them as the cogs turn."""
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        if d <= abs(a.r - b.r):
            return
        th = math.atan2(dy, dx)
        beta = math.acos((a.r - b.r) / d)
        move = run.angle.get(a, 0.0) * a.r
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
        self.rect(l, b, rt - l, t - b, (196, 164, 120), g)     # pegboard
        for gx in range(int(l) + 20, int(rt), 40):
            for gy in range(int(b) + 20, int(t), 40):
                self.disc((gx, gy), 2.5, (150, 120, 86), g)
        self.rect(0, 0, 1000, b - 6, (52, 40, 32), g)           # the tray
        self.rect(0, b - 8, 1000, 4, (30, 24, 20), g)
        # The bucket, its rope and the flag it has to reach.
        g = self.g()
        wx, wy = mc.winch
        rope_x = wx + model.DRUM
        top_y = model.FLOOR + mc.lift
        bucket_y = model.FLOOR + run.height
        self.rect(rope_x - 24, model.FLOOR - 4, 48, 4, (90, 70, 50), g)
        self.line((rope_x + 4, top_y + 26), (rope_x + 70, top_y + 26), 2,
                  (60, 140, 70), g)
        self.poly([(rope_x + 70, top_y + 26), (rope_x + 70, top_y + 46),
                   (rope_x + 90, top_y + 38)], (80, 190, 90), g)
        self.line((rope_x, wy), (rope_x, bucket_y + 30), 2, (90, 70, 40), g)
        self.line((rope_x - 14, bucket_y + 22), (rope_x, bucket_y + 30), 2,
                  (60, 60, 60), g)
        self.line((rope_x + 14, bucket_y + 22), (rope_x, bucket_y + 30), 2,
                  (60, 60, 60), g)
        self.poly([(rope_x - 16, bucket_y + 22), (rope_x + 16, bucket_y + 22),
                   (rope_x + 12, bucket_y), (rope_x - 12, bucket_y)],
                  (110, 120, 140), g)
        self.rect(rope_x - 16, bucket_y + 19, 32, 3, (160, 170, 190), g)
        if run.level.load > 0.5:
            self.words('%.1f' % run.level.load, rope_x, bucket_y + 8, 9,
                       colour=(255, 255, 255, 230), group=g)
        # The motor's case and the fan's blades, under the cogs.
        g = self.g()
        mx, my = mc.motor
        self.rect(mx - 46, my - 46, 92, 92, (60, 70, 90), g)
        self.rect(mx - 42, my - 42, 84, 84, (80, 92, 116), g)
        self.words(_('MOTOR'), mx, my - 60, 10, bold=True,
                   colour=(40, 40, 50, 255), group=g)
        self.disc((wx, wy), model.DRUM + 4, (90, 70, 50), g)    # drum
        self.disc((wx, wy), model.DRUM, (150, 120, 80), g)
        self.words(_('WINCH'), wx, wy + 84, 10, bold=True,
                   colour=(40, 40, 50, 255), group=g)
        if mc.fan is not None:
            fx, fy = mc.fan
            f = run.on(mc.fan)
            spin = run.angle.get(f, 0.0) if f is not None else 0.0
            for k in range(3):
                a = spin * 1.0 + 2 * math.pi * k / 3
                self.poly([(fx, fy), (fx + 50 * math.cos(a - 0.3),
                                      fy + 50 * math.sin(a - 0.3)),
                           (fx + 56 * math.cos(a + 0.1),
                            fy + 56 * math.sin(a + 0.1))],
                          (180, 210, 230), g)
            self.arrow(fx, fy, 66, mc.fan_way, (40, 120, 200), g)
            self.words(_('FAN'), fx, fy + 80, 10, bold=True,
                       colour=(40, 40, 50, 255), group=g)
        self.arrow(mx, my, 34, -1, (240, 200, 70), g)
        for p in run.pegs:                                      # axles
            if run.on(p, run.layer) is None:
                self.disc(p, 8, (60, 50, 40), g)
                self.disc(p, 5, (200, 180, 120), g)
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

    def _layers(self, run) -> None:
        """The back layer, then the front one raised over it: each
        layer's walls, cogs and chains; the layer not in hand is faint."""
        mc = run.machine
        two = run.level.layers > 1
        for z in (1, 0) if two else (0,):
            mine = z == run.layer
            alpha = 255 if mine or not two else (150 if z == 1 else 120)
            g = self.g()
            if z == 0 and two:                   # shadows on the back
                for c in run.cogs:
                    if c.z == 0:
                        self.disc((c.x + 7, c.y - 7), c.r, (0, 0, 0, 55), g)
                for w in mc.walls:
                    if w[4] == 0:
                        self.rect(w[0] + 7, w[1] - 7, w[2], w[3],
                                  (0, 0, 0, 55), g)
            g = self.g()
            for w in mc.walls:
                if w[4] != z:
                    continue
                wx, wy, ww, wh = w[:4]
                base = (90, 94, 104) if z == 0 else (70, 60, 52)
                self.rect(wx, wy, ww, wh, base + (alpha,), g)
                self.rect(wx + 3, wy + 3, ww - 6, wh - 6,
                          polish.lighter(base, 0.2) + (alpha,), g)
                for k in range(int(wh // 30) + 1):
                    self.disc((wx + ww / 2, wy + 10 + k * 30), 2.5,
                              (50, 50, 56, alpha), g)
            g = self.g()
            for c in run.cogs:
                if c.z != z:
                    continue
                colour = METALS.get(c.r, (180, 180, 180))
                if z == 1:
                    colour = polish.mix(colour, (60, 50, 44), 0.3)
                self.cog(c.x, c.y, c.r, run.angle.get(c, 0.0), colour, g,
                         alpha=alpha)
                if any(model.same_axle(c, o) for o in run.cogs):
                    self.disc((c.x, c.y), 9, (230, 200, 90, alpha), g)
                    self.disc((c.x, c.y), 4, (60, 50, 30, alpha), g)
            g = self.g()
            for a, b in run.chains:
                if a.z == z:
                    self.chain(run, a, b, alpha, g)
        if two:
            hud = pyglet.graphics.Group(order=890)
            for k, (z, name) in enumerate(((0, _('FRONT')), (1, _('BACK')))):
                on = z == run.layer
                x0 = 40 + 84 * k
                self.rect(x0, 600, 78, 22, ((240, 200, 70) if on
                                            else (90, 80, 70)), hud)
                self.words(name, x0 + 39, 611, 10, bold=True, group=hud,
                           colour=(30, 26, 20, 255) if on
                           else (200, 190, 180, 255))
            self.words(_('Tab: switch layer'), 300, 611, 10, group=hud,
                       colour=(255, 255, 255, 220))

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
