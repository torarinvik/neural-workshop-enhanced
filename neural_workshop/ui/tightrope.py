# -*- coding: utf-8 -*-
"""Tightrope on screen: the walker, the pole, and a long way down.

A 3D view from just behind the walker's shoulders: the wire runs away
in perspective to the far tower, over rooftops and streets a long way
down. The camera rides the wire, so when the wire swings or bounces the
whole city slides and bobs under you. The walker leans as the model's
lean says; the heavy pole follows the pointer a moment behind. Wind
shows as streaks and as the flag on the far tower, and a bird that
lands on the pole sits where it has to be clicked off. Along the top is
how far across you are.

Mouse: left and right carries the pole; click a bird to shoo it.
Keys: Space (or Up, or W) takes a step.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 takes a step.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Optional

import pyglet
from pyglet.window import key

from .. import tightrope as model
from ..i18n import _
from . import polish
from .handtask import HandTask


class Tightrope(HandTask):
    """Step by step across, upright."""

    instance: Optional['Tightrope'] = None

    TITLE = 'Tightrope'
    TASK_ID = 'tightrope'
    PREFIX = 'ROPE'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.SPACE: model.STEP, key.UP: model.STEP,
                  key.W: model.STEP}
    BACK = (30, 40, 70)
    FOOTNOTE = _('Mouse left and right: the pole   Space: a step   '
                 'Click a bird to shoo it   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Walk across: balance with the pole')
        return ok

    LENGTH = 70.0              # metres of wire, tower to tower
    DROP = 38.0                # metres down to the street
    FOCAL = 520.0
    HORIZON = 400.0
    BACK_OFF = 4.2             # the camera, behind the walker

    def _city(self):
        if getattr(self, '_blocks', None) is None:
            draw = random.Random(7)
            blocks = []
            for row in range(-3, 18):
                z = row * 9.0
                for side in (-1, 1):
                    for lane in range(3):
                        x = side * (9.0 + lane * 13.0 + draw.uniform(0, 3))
                        blocks.append((x, z + draw.uniform(-1, 1),
                                       draw.uniform(4, 7), draw.uniform(3, 7),
                                       draw.uniform(8, 30),
                                       polish.mix((46, 52, 80), (96, 90, 110),
                                                  draw.random())))
            self._blocks = blocks
        return self._blocks

    def _scene(self, run, s: float) -> None:
        level = run.level
        share = run.taken / max(1, level.steps)
        L, f, hz = self.LENGTH, self.FOCAL, self.HORIZON
        walk_z = 4.0 + share * (L - 8.0)
        shape_here = max(0.25, math.sin(math.pi * walk_z / L))
        cam = [run.swing * 0.6, 2.3 + run.boing * 0.35, walk_z - self.BACK_OFF]

        def at(za: float):              # the wire's sideways and up offset
            k = max(0.0, math.sin(math.pi * za / L)) / shape_here
            return (run.swing * 0.6 * min(k, 1.6),
                    run.boing * 0.35 * min(k, 1.6) - 1.2 * (k * shape_here - shape_here))

        def P(x, y, z):
            d = z - cam[2]
            if d < 0.4:
                return None
            return (500.0 + f * (x - cam[0]) / d, hz + f * (y - cam[1]) / d)

        # Sky and the hazy ground under the horizon.
        for k in range(8):
            self.rect(0, hz + (640 - hz) * k / 8, 1000, (640 - hz) / 8 + 1,
                      polish.mix((250, 180, 130), (50, 70, 130), k / 7.0),
                      self.g())
        for k in range(6):
            self.rect(0, hz * (1 - (k + 1) / 6), 1000, hz / 6 + 1,
                      polish.mix((120, 110, 130), (40, 44, 64), k / 5.0),
                      self.g())
        g = self.g()
        ground = -self.DROP
        for x in range(-60, 61, 12):            # the streets
            self.line(P(x, ground, cam[2] + 1.0), P(x, ground, 200.0), 1,
                      (90, 90, 110), g)
        for k in range(30):
            z = (k - 6) * 9.0 + 4.5
            self.line(P(-80, ground, z), P(80, ground, z), 1, (90, 90, 110), g)
        # Rooftops, far ones first, each a lit top and its near faces.
        blocks = sorted(self._city(), key=lambda b: -(b[1] - cam[2]))
        for x, z, w, d, h, c in blocks:
            if z + d < cam[2] + 1.0 or z > cam[2] + 160:
                continue
            gg = self.g()
            top = ground + h
            x0, x1, z0, z1 = x - w / 2, x + w / 2, z, z + d
            front = [P(x0, ground, z0), P(x1, ground, z0), P(x1, top, z0),
                     P(x0, top, z0)]
            self.poly(front, polish.mix(c, (0, 0, 0), 0.2), gg)
            sx = x0 if x > cam[0] else x1
            self.poly([P(sx, ground, z0), P(sx, ground, z1), P(sx, top, z1),
                       P(sx, top, z0)], polish.mix(c, (0, 0, 0), 0.45), gg)
            self.poly([P(x0, top, z0), P(x1, top, z0), P(x1, top, z1),
                       P(x0, top, z1)], polish.lighter(c, 0.25), gg)
            if z0 - cam[2] < 70:                # lit windows
                for row in range(2, int(h) - 1, 4):
                    for col in range(1, int(w) - 1, 2):
                        if (int(x * 7) + row * 3 + col) % 3:
                            continue
                        self.poly([P(x0 + col, ground + row, z0),
                                   P(x0 + col + 0.8, ground + row, z0),
                                   P(x0 + col + 0.8, ground + row + 1.4, z0),
                                   P(x0 + col, ground + row + 1.4, z0)],
                                  (250, 220, 130), gg)
        # The far tower, its platform and its flag.
        gg = self.g()
        wx, wy = at(L)
        for (a, b, c) in (((-2.5, 2.5), (L, L + 5), (70, 66, 80)),):
            self.poly([P(a[0], ground, b[0]), P(a[1], ground, b[0]),
                       P(a[1], 0.0, b[0]), P(a[0], 0.0, b[0])], c, gg)
            self.poly([P(a[1], ground, b[0]), P(a[1], ground, b[1]),
                       P(a[1], 0.0, b[1]), P(a[1], 0.0, b[0])],
                      polish.mix(c, (0, 0, 0), 0.4), gg)
            self.poly([P(-3.5, 0.0, b[0] - 1), P(3.5, 0.0, b[0] - 1),
                       P(3.5, 0.0, b[1] + 1), P(-3.5, 0.0, b[1] + 1)],
                      (200, 80, 70), gg)
        self.line(P(1.5, 0, L), P(1.5, 4.0, L), 2, (40, 40, 40), gg)
        blow = run.wind()
        flap = math.sin(run.t * 9) * 0.3
        tip = 1.5 + 2.2 * max(-1.0, min(1.0, blow / 1.2)) + 0.3
        self.poly([P(1.5, 4.0, L), P(tip, 3.6 + flap, L), P(1.5, 3.2, L)],
                  (240, 220, 80), gg)
        # The wire, in pieces so its swing and sag show.
        gg = self.g()
        prev = None
        for k in range(25):
            za = walk_z + (L - walk_z) * (k / 24.0) ** 1.5
            ox, oy = at(za)
            here = P(ox, oy, za)
            if prev is not None:
                self.line(prev, here, 3, (30, 30, 36), gg)
            prev = here
        fx, fy = at(walk_z)
        self.line(P(fx, fy, walk_z), P(at(walk_z - 2.5)[0], at(walk_z - 2.5)[1],
                                       walk_z - 2.5), 4, (30, 30, 36), gg)
        # Wind: streaks drifting past at a few depths.
        if abs(blow) > 0.05:
            gg = self.g()
            alpha = int(min(200, 60 + 110 * abs(blow)))
            way = 1 if blow > 0 else -1
            for k in range(14):
                depth = 3 + (k * 7 % 13)
                x = ((run.t * 9 * way * abs(blow) + k * 5.3) % 24) - 12
                y = -1.0 + (k * 3 % 7) * 0.7
                self.line(P(x, y, cam[2] + depth),
                          P(x - 1.2 * way, y, cam[2] + depth), 2,
                          (255, 255, 255, alpha), gg)
        # The walker, rolled about the feet by the lean.
        lean = run.lean
        base = P(fx, fy, walk_z)

        def up(h: float, side: float = 0.0):
            sx = side * math.cos(lean) + h * math.sin(lean)
            sy = h * math.cos(lean) - side * math.sin(lean)
            p = P(fx + sx, fy + sy, walk_z)
            return p if p is not None else base
        k = f / self.BACK_OFF / 162.0
        gg = self.g()
        self.oval((base[0], base[1] - 2), 26 * k, 6 * k, (0, 0, 0, 90), gg)
        for side in (-1, 1):                                # legs
            fwd = 0.12 * side * run.foot
            foot = P(fx + 0.06 * side, fy, walk_z + fwd)
            hip = up(0.92, 0.13 * side)
            self.poly([(foot[0] - 7 * k, foot[1]), (foot[0] + 7 * k, foot[1]),
                       (hip[0] + 13 * k, hip[1]), (hip[0] - 13 * k, hip[1])],
                      (40, 44, 70) if side < 0 else (52, 58, 90), gg)
            self.oval((foot[0], foot[1] + 3 * k), 10 * k, 6 * k, (20, 20, 24), gg)
        gg = self.g()
        self.poly([up(0.9, -0.2), up(0.9, 0.0), up(1.5, 0.0), up(1.5, -0.26)],
                  (170, 50, 60), gg)                        # shaded torso
        self.poly([up(0.9, 0.0), up(0.9, 0.2), up(1.5, 0.26), up(1.5, 0.0)],
                  (210, 70, 80), gg)
        self.poly([up(1.46, -0.27), up(1.46, 0.27), up(1.53, 0.2),
                   up(1.53, -0.2)], (230, 90, 100), gg)
        self.disc(up(1.62), 9 * k, (220, 186, 156), gg)          # neck
        self.disc(up(1.74), 21 * k, (236, 200, 170), gg)         # head
        self.oval(up(1.78), 22 * k, 17 * k, (60, 40, 30), gg)        # hair, from behind
        # The pole, where the model says, and the arms out to it.
        gg = self.g()
        mid = 500 + model.REACH * run.pole() * 0.35
        tilt = math.tan(lean) * 0.5

        def pole(x: float):
            return (x, 250.0 - (x - 500.0) * tilt)
        self.line(pole(mid - 0.75 * model.REACH),
                  pole(mid + 0.75 * model.REACH), 9, (150, 140, 110), gg)
        self.line(pole(mid - 0.75 * model.REACH),
                  pole(mid + 0.75 * model.REACH), 5, (240, 230, 196), gg)
        for end in (-1, 1):
            self.disc(pole(mid + end * 0.75 * model.REACH), 7, (90, 80, 70), gg)
        for side in (-1, 1):
            hand_at = pole(500 + 70 * side)
            self.line(up(1.45, 0.24 * side), hand_at, 9 * k, (190, 60, 70), gg)
            self.disc(hand_at, 8, (236, 200, 170), gg)
        gg = self.g()
        for end in run.perched:
            bx, by = run.bird_spot(end)
            self.oval((bx, by + 12), 16, 11, (40, 40, 50), gg)
            self.oval((bx - 3 * end, by + 14), 9, 6, (70, 70, 84), gg)
            self.disc((bx + 9 * end, by + 22), 7, (40, 40, 50), gg)
            self.poly([(bx + 15 * end, by + 23), (bx + 24 * end, by + 20),
                       (bx + 15 * end, by + 18)], (250, 180, 60), gg)
        hud = pyglet.graphics.Group(order=900)
        self.rect(250, 606, 500, 10, (20, 24, 40, 220), hud)
        self.rect(250, 606, 500 * share, 10, (110, 220, 140), hud)
        self.words(_('%d of %d steps') % (run.taken, level.steps), 500, 588,
                   12, group=hud, colour=(255, 255, 255, 230))
        if abs(lean) / model.FALL > 0.5:
            self.words(_('LEANING'), 500, 560, 14, bold=True, group=hud,
                       colour=(255, 120, 90, 255))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d steps') % (
            self.rung, self.trial, self.total_trials, run.level.steps)
