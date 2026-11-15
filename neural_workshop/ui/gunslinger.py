# -*- coding: utf-8 -*-
"""Gunslinger on screen: a street at sundown, seen down your own barrel.

The sun sits low over mesas at the end of the street, behind a church;
false-fronted buildings run down both sides with porches, lit windows
and painted signs, and everything throws a long shadow towards you. The
men stand in the street in long coats and coloured hats: a man's gun
arm hangs by his holster, twitches when he feints, and comes up level
when he draws. Your revolver is held out at the bottom of the picture
and its sight -- a ring with four ticks -- follows the pointer (and
wanders, on the higher rungs). The cylinder at the bottom left shows
the rounds left and a lamp for the hammer. The notice is nailed up
along the top. There is no clock on the screen: when he will draw is
the thing not known.

Mouse: aim, and click to shoot -- once he has gone for his gun. Keys:
Space cocks the hammer.

For the agent boundary: ports 0-11 move the sight (up, down, left,
right by 80, 20 or 5 units of a 1000 by 640 screen), 12 pulls the
trigger and 13 lets it go; port 14 cocks the hammer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import gunslinger as model
from ..i18n import _
from . import polish
from .handtask import HandTask

HAT = ((204, 52, 44), (26, 24, 28), (236, 230, 214), (52, 132, 70),
       (126, 82, 44), (60, 100, 196))
COATS = ((74, 60, 52), (98, 78, 58), (56, 62, 78), (88, 58, 56),
         (70, 74, 60), (60, 52, 66))
WOODS = ((150, 104, 70), (128, 92, 66), (164, 122, 84), (112, 80, 60),
         (142, 110, 86), (120, 96, 78))
SIGNS = ('SALOON', 'BANK', 'HOTEL', 'SHERIFF', 'STORE', 'LIVERY', 'BARBER',
         'ASSAY', 'STAGE', 'SMITH', 'FEED', 'POST')
SKIN = (222, 178, 140)
STEEL = (58, 60, 68)
DUSK = (255, 150, 70)                 # the light everything is tinted by


class Gunslinger(HandTask):
    """Fire when he draws, not before, and be the quicker."""

    instance: Optional['Gunslinger'] = None

    TITLE = 'Gunslinger'
    TASK_ID = 'gunslinger'
    PREFIX = 'GUN'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.SPACE: model.COCK}
    BACK = (40, 26, 30)
    TIME_BAR = False
    DRAW_POINTER = False
    FOOTNOTE = _('Mouse: aim   Click: shoot, once he has gone for his gun'
                 '   Space: cock the hammer   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Hold your fire until he goes for his gun')
        return ok

    def _g(self):
        self.layer += 1
        return pyglet.graphics.Group(order=self.layer)

    # --- the picture ---------------------------------------------------------------

    def _scene(self, run, s: float) -> None:
        view = run.view()
        self.layer = 0
        self._sky(run, view)
        self._street(run, view)
        for side in (-1, 1):
            for n in range(5, -1, -1):
                self._building(view, side, n)
        men = sorted(range(len(run.duel.men)),
                     key=lambda j: -run.duel.men[j].z)
        for j in men:
            self._shadow(run, j, view)
        self._tumbleweed(run, view)
        for j in men:
            self._man(run, j, view)
        thick = run.dust()
        if thick > 0.01:
            self.rect(0, 0, 1000, 640, (226, 190, 140, int(255 * thick)),
                      self._g())
        self._gun(run)
        self._sight(run)
        self._hud(run)

    def _sky(self, run, view) -> None:
        ox, oy, k = self.fit
        far = view.see((0.0, 0.0, -600.0))
        self.horizon = h = far[1] if far else 300.0
        G = pyglet.graphics.Group
        polish.gradient(self.drawn, self.batch, ox, oy + h * k, 1000 * k,
                        (640 - h) * k, (255, 176, 92), (58, 44, 104),
                        bands=26, group=G(order=-24))
        sun = view.see((-14.0, 5.0, -120.0))
        if sun is not None:
            x, y = self.px(sun[0], sun[1])
            for r, a in ((150, 26), (100, 40), (62, 70)):
                polish.glow(self.drawn, self.batch, x, y, r * k,
                            (255, 214, 140), strength=a, group=G(order=-23))
            self.disc(sun, 34, (255, 236, 190), G(order=-22))
        for n in range(7):                              # streaks of cloud
            cx = (n * 173 + 60 + run.t * 2.0) % 1100 - 50
            cy = h + 120 + (n * 71) % 190
            w = 120 + (n * 53) % 140
            self.poly([(cx - w, cy), (cx - w * 0.5, cy + 7), (cx + w * 0.6,
                                                              cy + 5),
                       (cx + w, cy - 1), (cx + w * 0.4, cy - 6),
                       (cx - w * 0.6, cy - 5)],
                      (255, 150 + 10 * (n % 3), 120, 70), G(order=-21))
        # Mesas along the horizon, the nearer ones darker.
        for tone, base, lift, seed in (((122, 78, 110), 0, 1.0, 3),
                                       ((92, 56, 84), -4, 0.7, 8)):
            x = -40.0
            n = seed
            while x < 1040:
                n = (n * 37 + 11) % 101
                w = 70 + n * 1.4
                top = h + base + lift * (18 + (n * 13) % 46)
                self.poly([(x, h - 1), (x + 10, top), (x + w - 14, top),
                           (x + w, h - 1)], tone, G(order=-20))
                x += w + (n % 5) * 14 - 20

    def _street(self, run, view) -> None:
        ox, oy, k = self.fit
        h = self.horizon
        G = pyglet.graphics.Group
        polish.gradient(self.drawn, self.batch, ox, oy, 1000 * k, h * k,
                        (150, 104, 66), (236, 182, 112), bands=18,
                        group=G(order=-19))
        see = view.see
        # A church at the end of the street, against the sun.
        dark = (58, 36, 52)
        for quad in ([(-3, 0), (3, 0), (3, 4.5), (-3, 4.5)],
                     [(-1, 4.5), (1, 4.5), (1, 8.5), (-1, 8.5)]):
            self.poly([see((x, y, -62.0)) for x, y in quad], dark,
                      G(order=-18))
        self.poly([see((-3.4, 4.5, -62.0)), see((3.4, 4.5, -62.0)),
                   see((0.0, 6.6, -62.0))], dark, G(order=-17))
        self.poly([see((-1.2, 8.5, -62.0)), see((1.2, 8.5, -62.0)),
                   see((0.0, 11.5, -62.0))], dark, G(order=-17))
        # Wheel ruts and hoof marks.
        for x in (-1.6, -0.9, 0.9, 1.6):
            self.line(see((x, 0.0, -2.5)), see((x * 0.9, 0.0, -60.0)), 2,
                      (140, 98, 62, 110), G(order=-16))
        for n in range(40):
            a = (n * 61) % 97 / 97.0
            b = (n * 29) % 89 / 89.0
            p = see(((a - 0.5) * 11.0, 0.0, -3.0 - b * 40.0))
            if p is not None:
                self.rect(p[0], p[1], max(2.0, 40.0 / p[2]),
                          max(1.0, 12.0 / p[2]), (128, 88, 56, 120),
                          G(order=-15))
        for side in (-1, 1):                            # telegraph poles
            for z in (-9.0, -22.0, -35.0, -48.0):
                x = side * 5.2
                self.line(see((x, 0, z)), see((x, 6.2, z)), 3, (70, 48, 40),
                          G(order=-14))
                self.line(see((x - 0.6, 5.6, z)), see((x + 0.6, 5.6, z)), 2,
                          (70, 48, 40), G(order=-14))

    def _building(self, view, side: int, n: int) -> None:
        see = view.see
        z0 = -5.0 - 7.2 * n
        z1 = z0 - 6.6
        pick = (n * 5 + (2 if side > 0 else 0)) % len(WOODS)
        wood = polish.mix(WOODS[pick], DUSK, 0.18)
        if side > 0:                        # the right side is in shade
            wood = polish.mix(wood, (40, 24, 50), 0.35)
        tall = 5.0 + 1.2 * ((n * 7 + side) % 3)
        x, out = side * 7.0, side * 12.5
        g = self._g
        at = lambda f, y, dx=0.0: see((x + dx * side, y,                 # noqa
                                       z0 + (z1 - z0) * f))
        # The end wall, facing up the street, and its sign.
        end = polish.mix(wood, (30, 18, 30), 0.3)
        self.poly([see((x, 0, z0)), see((out, 0, z0)), see((out, tall, z0)),
                   see((x, tall, z0))], end, g())
        # The street wall with its false front.
        self.poly([at(0, 0), at(1, 0), at(1, tall), at(0, tall)], wood, g())
        self.poly([at(0, tall), at(1, tall), at(1, tall + 0.25),
                   at(0, tall + 0.25)], polish.mix(wood, (0, 0, 0), 0.35),
                  g())
        for k in range(1, 9):                           # planking
            f = k / 9.0
            self.line(at(f, 0.3), at(f, tall), 1,
                      polish.mix(wood, (0, 0, 0), 0.22) + (150,), g())
        glass = (255, 208, 120) if (n + side) % 2 else (46, 40, 62)
        for f0 in (0.12, 0.62):                         # upstairs windows
            frame = [at(f0, 3.3), at(f0 + 0.24, 3.3), at(f0 + 0.24, 4.5),
                     at(f0, 4.5)]
            self.poly(frame, polish.mix(wood, (0, 0, 0), 0.5), g())
            self.poly([at(f0 + 0.03, 3.42), at(f0 + 0.21, 3.42),
                       at(f0 + 0.21, 4.38), at(f0 + 0.03, 4.38)], glass, g())
            self.line(at(f0 + 0.12, 3.42), at(f0 + 0.12, 4.38), 1,
                      (40, 28, 30), g())
        self.poly([at(0.4, 0.3), at(0.58, 0.3), at(0.58, 2.3), at(0.4, 2.3)],
                  (48, 32, 34), g())                    # the door
        self.poly([at(0.1, 0.9), at(0.32, 0.9), at(0.32, 2.1), at(0.1, 2.1)],
                  (255, 196, 110) if (n + side) % 3 else (46, 40, 62), g())
        # The boardwalk and the porch over it.
        walk = polish.mix((120, 92, 70), DUSK, 0.15)
        self.poly([at(0, 0.3), at(1, 0.3), at(1, 0.3, -1.7),
                   at(0, 0.3, -1.7)], walk, g())
        self.poly([at(0, 0.0, -1.7), at(1, 0.0, -1.7), at(1, 0.3, -1.7),
                   at(0, 0.3, -1.7)], polish.mix(walk, (0, 0, 0), 0.4), g())
        for f in (0.03, 0.5, 0.97):
            self.line(at(f, 0.3, -1.6), at(f, 2.7, -1.6), 3, (70, 48, 40),
                      g())
        self.poly([at(0, 3.0), at(1, 3.0), at(1, 2.65, -1.8),
                   at(0, 2.65, -1.8)], polish.mix(wood, (30, 16, 24), 0.45),
                  g())
        # The painted sign, on the end wall where it can be read.
        a, b = see((x + side * 0.6, tall - 1.5, z0)), \
            see((out - side * 0.6, tall - 0.5, z0))
        if a is not None and b is not None:
            self.poly([a, (b[0], a[1]), b, (a[0], b[1])], (232, 214, 170),
                      g())
            wide = abs(b[0] - a[0])
            if 40 < wide and min(a[0], b[0]) > 15 and \
                    max(a[0], b[0]) < 985 and max(a[1], b[1]) < 560:
                word = SIGNS[(n * 2 + (1 if side > 0 else 0)) % len(SIGNS)]
                self.words(word, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
                           min(abs(b[1] - a[1]) * 0.55,
                               wide / (len(word) * 0.95)),
                           group=g(), bold=True, colour=(70, 34, 26, 255))

    def _shadow(self, run, j, view) -> None:
        """His shadow, thrown towards you by the low sun."""
        see = view.see
        x, _y, z = run.stands(j)
        if run.fell == j:
            return
        tip = (x + 1.2, 0.0, z + 5.5)
        self.poly([see((x - 0.3, 0.0, z)), see((x + 0.3, 0.0, z)),
                   see((tip[0] + 0.45, 0.0, tip[2])),
                   see((tip[0] - 0.45, 0.0, tip[2]))], (70, 40, 44, 110),
                  self._g())

    def _tumbleweed(self, run, view) -> None:
        if run.level.rung < 4:
            return
        u = (run.t * 0.11) % 1.0
        x, z = -9.0 + 18.0 * u, -7.5
        hop = 0.35 + 0.3 * abs(math.sin(run.t * 3.0))
        q = view.see((x, hop, z))
        if q is None:
            return
        r = view.size(0.35, q[2])
        g = self._g()
        self.disc(q, r, (150, 112, 70, 150), g)
        for n in range(6):
            a = run.t * 4.0 + n * 1.05
            self.line((q[0] - r * math.cos(a), q[1] - r * math.sin(a)),
                      (q[0] + r * math.cos(a), q[1] + r * math.sin(a)), 1.5,
                      (104, 74, 46), g)

    def _man(self, run, j, view) -> None:
        see = view.see
        x, _y, z = run.stands(j)
        feet = see((x, 0.0, z))
        if feet is None:
            return
        u = view.size(1.0, feet[2])                  # a metre, in units
        cx, by = feet[0], feet[1]
        g = self._g
        coat = polish.mix(COATS[j % len(COATS)], DUSK, 0.12)
        dark = polish.mix(coat, (0, 0, 0), 0.45)
        hat = HAT[run.duel.men[j].hat]

        def P(*pts):
            return [(cx + a * u, by + b * u) for a, b in pts]

        if run.fell == j:                            # on his back in the dust
            self.poly(P((-0.95, 0.0), (0.75, 0.0), (0.8, 0.3), (-0.9, 0.34)),
                      coat, g())
            self.disc((cx + 0.95 * u, by + 0.17 * u), 0.15 * u, SKIN, g())
            self.poly(P((-1.3, 0.0), (-0.95, 0.0), (-0.95, 0.2),
                        (-1.3, 0.26)), (40, 30, 30), g())
            self._hat(cx + 1.45 * u, by, u, hat, g, tilt=True)
            return
        if j in run.hatless:                         # his hat, in the dust
            self._hat(cx - 0.9 * u, by - 0.02 * u, u, hat, g, tilt=True)
        for side in (-1, 1):                         # boots and legs
            lx = side * 0.17
            self.poly(P((lx - 0.1, 0.0), (lx + 0.16, 0.0), (lx + 0.1, 0.34),
                        (lx - 0.09, 0.34)), (36, 26, 26), g())
            self.poly(P((lx - 0.1, 0.3), (lx + 0.1, 0.3), (lx + 0.09 - side
                                                           * 0.04, 0.95),
                        (lx - 0.09 - side * 0.04, 0.95)), (52, 44, 50), g())
        # The long coat, open over a shirt, with a gun belt across it.
        self.poly(P((-0.33, 0.52), (0.33, 0.52), (0.29, 1.52), (-0.29,
                                                                1.52)),
                  coat, g())
        self.poly(P((-0.1, 0.9), (0.1, 0.9), (0.07, 1.5), (-0.07, 1.5)),
                  (214, 200, 176), g())
        self.poly(P((-0.33, 0.52), (-0.1, 0.52), (-0.09, 1.5), (-0.29,
                                                                1.52)),
                  dark + (120,), g())
        self.poly(P((-0.31, 0.9), (0.31, 0.84), (0.31, 0.93), (-0.31,
                                                               0.99)),
                  (60, 36, 22), g())
        self.rect(cx - 0.035 * u, by + 0.89 * u, 0.07 * u, 0.07 * u,
                  (220, 190, 90), g())
        self.poly(P((-0.3, 1.5), (0.3, 1.5), (0.22, 1.58), (-0.22, 1.58)),
                  dark, g())                         # shoulders
        self.poly(P((-0.12, 1.47), (0.12, 1.47), (0.0, 1.33)),
                  (170, 40, 36), g())                # bandana
        self.rect(cx - 0.05 * u, by + 1.55 * u, 0.1 * u, 0.08 * u, SKIN,
                  g())
        self.disc((cx, by + 1.71 * u), 0.135 * u, SKIN, g())
        self.rect(cx - 0.13 * u, by + 1.62 * u, 0.26 * u, 0.05 * u,
                  (60, 40, 30), g())                 # moustache and shade
        if j not in run.hatless:
            self._hat(cx, by + 1.8 * u, u, hat, g)
        # The off arm hangs; the gun arm hangs, reaches, or comes level.
        self.poly(P((-0.36, 1.5), (-0.27, 1.5), (-0.3, 0.92), (-0.4, 0.92)),
                  dark, g())
        self.disc((cx - 0.35 * u, by + 0.88 * u), 0.05 * u, SKIN, g())
        arm = run.arm(j)
        sx, sy = cx + 0.31 * u, by + 1.47 * u
        a = -math.pi / 2 + 0.12 + arm * (math.pi / 2 + 0.05)
        reach = 0.6 * u * (1.0 - 0.45 * arm)
        ex, ey = sx + reach * math.cos(a), sy + reach * math.sin(a)
        if arm < 0.75:                               # holster and its gun
            self.poly(P((0.27, 0.62), (0.4, 0.62), (0.39, 0.9),
                        (0.28, 0.9)), (70, 42, 24), g())
            self.rect(cx + 0.3 * u, by + 0.88 * u, 0.07 * u, 0.1 * u,
                      (30, 28, 30), g())
        self.line((sx, sy), (ex, ey), max(2.5, 0.13 * u), dark, g())
        self.disc((ex, ey), max(2.0, 0.055 * u), SKIN, g())
        if arm >= 0.75:
            self.disc((ex, ey), max(3.0, 0.085 * u), (24, 24, 28), g())
            self.disc((ex, ey), max(1.2, 0.035 * u), (0, 0, 0), g())
            lost = run.result is not None and not run.result[0] and \
                run.fell is None and j == run.duel.foe and \
                run.t >= run.end - 0.05
            if lost:                                 # his shot
                for r, c in ((0.5, (255, 200, 80, 150)),
                             (0.28, (255, 244, 200, 230))):
                    self.disc((ex, ey), r * u, c, g())

    def _hat(self, x, y, u, colour, g, tilt=False) -> None:
        d = 0.05 * u if tilt else 0.0
        band = polish.mix(colour, (0, 0, 0), 0.5)
        self.poly([(x - 0.36 * u, y - d), (x + 0.36 * u, y + d),
                   (x + 0.3 * u, y + 0.06 * u + d), (x - 0.3 * u,
                                                     y + 0.06 * u - d)],
                  colour, g())
        self.poly([(x - 0.2 * u, y + 0.05 * u), (x + 0.2 * u, y + 0.05 * u),
                   (x + 0.17 * u, y + 0.3 * u), (x, y + 0.26 * u),
                   (x - 0.17 * u, y + 0.3 * u)], colour, g())
        self.rect(x - 0.2 * u, y + 0.06 * u, 0.4 * u, 0.05 * u, band, g())

    def _gun(self, run) -> None:
        """Your own revolver, held out towards the sight."""
        g = self._g
        ax, ay = run.aim()
        kick = 0.0
        if run.shots and run.t - run.shots[-1][0] < 0.14:
            kick = 1.0 - (run.t - run.shots[-1][0]) / 0.14
        bx = 650.0 + 0.4 * (ax - 500.0)              # where the hand is
        by = -130.0 + 0.08 * ay + 30.0 * kick
        tx = bx + 0.3 * (ax - bx)                    # the muzzle
        ty = min(by + 290.0 + 0.2 * (ay - 300.0), ay - 130.0) \
            + 36.0 * kick
        nx, ny = ty - by, -(tx - bx)
        d = math.hypot(nx, ny) or 1.0
        nx, ny = nx / d, ny / d

        def along(f, w):
            px, py = bx + (tx - bx) * f, by + (ty - by) * f
            return (px + nx * w, py + ny * w)

        self.poly([(bx - 150, -10), (bx + 230, -10), along(0.2, 78.2),
                   along(0.2, -78.2)], (66, 50, 44), g())           # sleeve
        self.poly([along(0.12, 74.8), along(0.5, 61.2), along(0.5, -61.2),
                   along(0.12, -74.8)], SKIN, g())                   # hand
        self.poly([along(0.3, 51), along(0.62, 51), along(0.62, -51),
                   along(0.3, -51)], (84, 52, 30), g())            # grip
        self.poly([along(0.55, 57.8), along(0.8, 51), along(0.8, -51),
                   along(0.55, -57.8)], STEEL, g())                  # cylinder
        for w in (-18, 0, 18):
            self.line(along(0.57, w * 1.7), along(0.79, w * 1.5), 2,
                      (30, 30, 36), g())
        self.poly([along(0.78, 22.1), along(1.0, 17), along(1.0, -17),
                   along(0.78, -22.1)], polish.mix(STEEL, (255, 255, 255),
                                                 0.12), g())       # barrel
        self.poly([along(0.97, 6.8), along(1.04, 5.1), along(1.04, -5.1),
                   along(0.97, -6.8)], (20, 20, 24), g())            # foresight
        back = 0.42 if run.cocked else 0.52
        self.poly([along(back, 11.9), along(back + 0.1, 10.2),
                   along(back + 0.1, -10.2), along(back, -11.9)], (28, 28, 32),
                  g())                                             # hammer
        self.poly([along(0.34, 68), along(0.5, 74.8), along(0.5, 37.4),
                   along(0.36, 34)], polish.mix(SKIN, (0, 0, 0), 0.12),
                  g())                                             # thumb
        if kick > 0.4:
            mx, my = along(1.08, 0)
            for r, c in ((110, (255, 190, 70, 140)), (60, (255, 240, 190,
                                                           230))):
                self.disc((mx, my), r * kick, c, g())

    def _sight(self, run) -> None:
        ax, ay = run.aim()
        g_under, g_top = self._g(), self._g()
        ring = [(ax + 17 * math.cos(a), ay + 17 * math.sin(a))
                for a in (2 * math.pi * k / 28 for k in range(29))]
        for group, thick, colour in ((g_under, 5.0, (0, 0, 0, 170)),
                                     (g_top, 2.2, (255, 250, 235, 255))):
            for a, b in zip(ring, ring[1:]):
                self.line(a, b, thick, colour, group)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                self.line((ax + dx * 9, ay + dy * 9),
                          (ax + dx * 27, ay + dy * 27), thick, colour, group)
        self.disc((ax, ay), 2.4, (255, 60, 40), g_top)

    def _hud(self, run) -> None:
        G = pyglet.graphics.Group
        hud, text = G(order=9000), G(order=9001)
        for t, x, y in run.shots:                       # where a round went
            if run.t - t < 0.1:
                self.disc((x, y), 12, (255, 240, 190, 200), hud)
        # The cylinder, and a lamp for the hammer.
        self.disc((70, 70), 40, (30, 28, 32, 230), hud)
        self.disc((70, 70), 36, (88, 90, 100), text)
        self.disc((70, 70), 6, (30, 28, 32), G(order=9002))
        for n in range(model.BULLETS):
            a = math.pi / 2 + 2 * math.pi * n / model.BULLETS
            self.disc((70 + 22 * math.cos(a), 70 + 22 * math.sin(a)), 8,
                      (232, 186, 84) if n < run.bullets else (34, 32, 36),
                      G(order=9002))
        if run.level.cock:
            self.rect(120, 52, 116, 30, (30, 20, 16, 220), hud)
            self.disc((136, 67), 7, (110, 240, 130) if run.cocked
                      else (230, 70, 50), text)
            self.words(_('COCKED') if run.cocked else _('SPACE'), 186, 67,
                       12, bold=True, group=text,
                       colour=(255, 240, 210, 255))
        # The notice, nailed up.
        self.rect(36, 572, 928, 58, (60, 36, 24), hud)
        self.rect(42, 577, 916, 48, (236, 218, 176), text)
        for x in (54, 946):
            self.disc((x, 601), 4, (60, 50, 50), G(order=9002))
        self.words(run.duel.notice, 500, 601,
                   min(17.0, 1080.0 / max(1, len(run.duel.notice))), bold=True,
                   group=G(order=9002), colour=(64, 30, 20, 255))
        if run.level.word and run.drawn() and run.result is None:
            self.words(_('DRAW!'), 503, 487, 54, bold=True, group=text,
                       colour=(40, 10, 10, 255))
            self.words(_('DRAW!'), 500, 490, 54, bold=True,
                       group=G(order=9002), colour=(255, 70, 40, 255))
        if run.result is not None and not run.result[0] and \
                run.fell is None and run.t >= run.end - 0.05:
            self.rect(0, 0, 1000, 640, (200, 20, 20, 90), text)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d rounds') % (
            self.rung, self.trial, self.total_trials, run.bullets)
