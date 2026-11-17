# -*- coding: utf-8 -*-
"""Claw Machine on screen: the cabinet from the front.

The floor with its prizes, the glass edges, the trolley rail at the top
and the claw on its cable. On rung 1 a side view sits in the corner;
on the low rungs the claw's shadow lies on the floor under it.

Arrows or WASD move the trolley (Up is in, away from you); Space or
Enter drops the claw.

For the agent boundary: ports 0-3 move the trolley left, right, in and
out; port 4 drops.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key

from .. import clawmachine as model
from ..i18n import _
from .livetask import LiveTask

H, D, T = model.HALF, model.DEEP, model.TOP


class ClawMachine(LiveTask):
    """Grab the gold prize."""

    instance: Optional['ClawMachine'] = None

    TITLE = 'Claw Machine'
    TASK_ID = 'claw_machine'
    PREFIX = 'CLAW'
    CATEGORY = 'perception'
    MODEL = model
    BACK = (40, 20, 50)
    EVENT_KEYS = {key.SPACE: model.DROP, key.RETURN: model.DROP,
                  key.ENTER: model.DROP}
    FOOTNOTE = _('Arrows / WASD: move (Up is in)   Space: drop   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Drop the claw over the gold prize')
        return ok

    def _held(self):
        k = self.keys
        for keys, port in (((key.LEFT, key.A), model.LEFT),
                           ((key.RIGHT, key.D), model.RIGHT),
                           ((key.UP, key.W), model.IN),
                           ((key.DOWN, key.S), model.OUT)):
            if any(k[s] for s in keys):
                return port
        return None

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height)
        eye = (0.0, 1.15, -2.9) if run.level.low else (0.0, 2.3, -2.5)
        aim = (0.0, 0.55, 0.8)
        look = tuple(a - e for a, e in zip(aim, eye))
        lens = self.camera(eye, look, left, bottom, width, height, 52.0)
        g = self.layer()
        self.face(lens, [(-H, 0, D), (H, 0, D), (H, 2.0, D), (-H, 2.0, D)],
                  (70, 40, 80), g)
        for x in (-H, H):
            self.face(lens, [(x, 0, 0), (x, 0, D), (x, 2.0, D), (x, 2.0, 0)],
                      (58, 34, 68), g)
        self.face(lens, [(-H, 0, 0), (H, 0, 0), (H, 0, D), (-H, 0, D)],
                  (120, 100, 130), g)
        g = self.layer()
        for k in range(1, 8):
            z = D * k / 8
            self.seg(lens, (-H, 0.002, z), (H, 0.002, z), 1,
                     (140, 120, 150), g)
        cx, cz = run.claw()
        if run.level.shadow:
            self.face(lens, [(cx + 0.09 * math.cos(a), 0.003,
                              cz + 0.09 * math.sin(a))
                             for a in [i * math.pi / 8 for i in range(16)]],
                      (60, 45, 70), self.layer())
        prizes = sorted(run.cab.prizes,
                        key=lambda p: -run.prize_at(p)[1])
        held = run.result is not None and run.result[0]
        for p in prizes:
            px, pz = run.prize_at(p)
            if held and p is run.cab.prizes[0]:
                continue
            self.ball(lens, (px, p.r, pz), p.r, p.colour, self.layer())
        g = self.layer()
        self.seg(lens, (-H, T + 0.1, run.z), (H, T + 0.1, run.z), 4,
                 (150, 150, 160), g)
        self.box(lens, run.x - 0.08, T + 0.05, run.z - 0.08, run.x + 0.08,
                 T + 0.15, run.z + 0.08, (180, 180, 190), g)
        cy = T - run.depth
        self.seg(lens, (run.x, T + 0.05, run.z), (cx, cy, cz), 2,
                 (210, 210, 220), g)
        for a in (0.0, 2.1, 4.2):
            tip = (cx + 0.1 * math.cos(a), cy - 0.14, cz + 0.1 * math.sin(a))
            self.seg(lens, (cx, cy, cz), tip, 3, (220, 220, 230), g)
        if held:
            gold = run.cab.prizes[0]
            self.ball(lens, (cx, cy - 0.12, cz), gold.r, gold.colour, g)
        g = self.layer()
        for a, b in (((-H, 0, 0), (-H, 2.0, 0)), ((H, 0, 0), (H, 2.0, 0)),
                     ((-H, 2.0, 0), (H, 2.0, 0))):
            self.seg(lens, a, b, 3, (200, 220, 255, 140), g)
        if run.level.side:
            self._side(run, left + width - 230, bottom + 20, 210, 170)

    def _side(self, run, x0, y0, w, h) -> None:
        """The cabinet from the side: depth across, height up."""
        g = self.layer()
        self.rect(x0, y0, w, h, (20, 16, 26), g)

        def at(z, y):
            return x0 + 10 + (w - 20) * z / D, y0 + 10 + (h - 20) * y / 2.0

        self.line(at(0, 0), at(D, 0), 2, (150, 130, 160), g)
        for p in run.cab.prizes:
            px, pz = run.prize_at(p)
            self.disc(at(pz, p.r), p.r * (w - 20) / D, p.colour, g)
        cx, cz = run.claw()
        self.line(at(run.z, T + 0.1), at(cz, T - run.depth), 2,
                  (210, 210, 220), g)
        self.disc(at(cz, T - run.depth), 5, (230, 230, 240), g)
        self.say(_('side view'), x0 + w / 2, y0 + h - 10, 9,
                 (200, 200, 210, 200))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   %.0f s') % (
            self.rung, self.trial, self.total_trials,
            max(0.0, self.run.cab.seconds - self.run.t))
