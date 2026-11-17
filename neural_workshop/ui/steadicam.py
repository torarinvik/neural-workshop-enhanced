# -*- coding: utf-8 -*-
"""Steadicam on screen: the viewfinder.

What the camera sees, with the framing box drawn on it, and on the
rungs that ask for a size, two marks for the least and most of the
frame's height the walker may fill. The box turns green while the
walker is framed.

Arrows or WASD pan and tilt; Q / E (or the wheel) zoom; dragging pans
and tilts too.

For the agent boundary: ports 0-5 pan left / right, tilt up / down,
zoom in / out.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key, mouse

from .. import steadicam as model
from ..i18n import _
from .livetask import LiveTask

SHIRTS = ((220, 70, 60), (70, 120, 230), (240, 200, 60), (80, 190, 110))


class Steadicam(LiveTask):
    """Keep them in the frame."""

    instance: Optional['Steadicam'] = None

    TITLE = 'Steadicam'
    TASK_ID = 'steadicam'
    PREFIX = 'STEADY'
    CATEGORY = 'attention'
    MODEL = model
    BACK = (20, 22, 26)
    FOOTNOTE = _('Arrows / WASD: pan and tilt   Q / E or wheel: zoom   '
                 'Esc: menu')

    def _held(self):
        k = self.keys
        for keys, port in (((key.LEFT, key.A), model.PAN_L),
                           ((key.RIGHT, key.D), model.PAN_R),
                           ((key.UP, key.W), model.TILT_U),
                           ((key.DOWN, key.S), model.TILT_D),
                           ((key.E,), model.ZOOM_IN),
                           ((key.Q,), model.ZOOM_OUT)):
            if any(k[s] for s in keys):
                return port
        return None

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)
        run = self.run
        if run is not None and self.phase == self.PLAY and \
                buttons & mouse.LEFT:
            k = run.fov / 900.0
            run.yaw += dx * k
            run.pitch = max(-0.6, min(0.6, run.pitch + dy * k))

    def on_mouse_scroll(self, x, y, sx, sy):
        run = self.run
        if run is not None and self.phase == self.PLAY:
            run.fov = max(model.FOV[0], min(model.FOV[1],
                                            run.fov * math.exp(-0.08 * sy)))

    def _tick(self) -> None:
        run = self.run
        if run is not None:
            if run.level.people > 1:
                self.message = _('Follow the %s one') % \
                    model.COLOURS[run.whom()]
            else:
                self.message = _('Keep the walker in the box')
        super()._tick()

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        w = min(width, height / model.ASPECT)
        h = w * model.ASPECT
        x0, y0 = left + (width - w) / 2, bottom + (height - h) / 2
        self.frame(x0, y0, w, h, (30, 34, 40))
        look = (math.sin(run.yaw) * math.cos(run.pitch), math.sin(run.pitch),
                math.cos(run.yaw) * math.cos(run.pitch))
        lens = self.camera((0.0, model.EYE, 0.0), look, x0, y0, w, h,
                           math.degrees(run.fov))
        g = self.layer()
        self.rect(x0, y0, w, h, (150, 190, 230), g)
        g = self.layer()
        for k in range(8):
            z0, z1 = 2 + 6 * k, 8 + 6 * k
            c = (88 - 3 * k, 140 - 4 * k, 80 - 2 * k)
            self.face(lens, [(-40, 0, z0), (40, 0, z0), (40, 0, z1),
                             (-40, 0, z1)], c, g)
        things = [(math.hypot(tx, tz), 'tree', (tx, tz, r))
                  for tx, tz, r in run.park.trees]
        for k, wk in enumerate(run.park.walkers):
            px, pz = model.where(wk, run.t)
            things.append((math.hypot(px, pz), 'walker', (px, pz, k)))
        things.sort(key=lambda q: -q[0])
        for _d, kind, (a, b, c) in things:
            g = self.layer()
            if kind == 'tree':
                self.face(lens, [(a - c * 0.4, 0, b), (a + c * 0.4, 0, b),
                                 (a + c * 0.4, 3.0, b), (a - c * 0.4, 3.0, b)],
                          (90, 64, 44), g)
                self.ball(lens, (a, 4.2, b), 1.8 + c, (52, 110, 58), g, 0.3)
            else:
                shirt = SHIRTS[c % len(SHIRTS)] if run.level.people > 1 \
                    else SHIRTS[0]
                self.face(lens, [(a - 0.18, 0, b), (a + 0.18, 0, b),
                                 (a + 0.18, 0.85, b), (a - 0.18, 0.85, b)],
                          (50, 50, 70), g)
                self.face(lens, [(a - 0.24, 0.85, b), (a + 0.24, 0.85, b),
                                 (a + 0.24, 1.5, b), (a - 0.24, 1.5, b)],
                          shirt, g)
                self.ball(lens, (a, 1.63, b), 0.13, (230, 190, 160), g)
        # the viewfinder
        g = self.layer()
        ax, ay = run.aim()
        box = run.level.box
        bw = box * w / 2
        bh = box / model.ASPECT * 0.7 * h / 2
        cx = x0 + w / 2 + ax * w / 2
        cy = y0 + h / 2 + ay * h / 2
        ok = run.in_frame()
        col = (110, 240, 140, 230) if ok else (255, 255, 255, 200)
        for (p, q) in (((cx - bw, cy - bh), (cx + bw, cy - bh)),
                       ((cx + bw, cy - bh), (cx + bw, cy + bh)),
                       ((cx + bw, cy + bh), (cx - bw, cy + bh)),
                       ((cx - bw, cy + bh), (cx - bw, cy - bh))):
            self.line(p, q, 2, col, g)
        lo, hi = run.level.size
        if hi:
            for share, c in ((lo, (255, 220, 120, 200)),
                             (hi, (255, 160, 90, 200))):
                hh = share * h / 2
                self.line((x0 + 14, y0 + h / 2 - hh), (x0 + 14, y0 + h / 2 + hh),
                          4 if share == lo else 2, c, g)
        self.line((x0 + w / 2 - 8, y0 + h / 2), (x0 + w / 2 + 8, y0 + h / 2),
                  1, (255, 255, 255, 120), g)
        self.line((x0 + w / 2, y0 + h / 2 - 8), (x0 + w / 2, y0 + h / 2 + 8),
                  1, (255, 255, 255, 120), g)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        share = run.framed / max(1e-6, run.counted)
        return _('rung %d  %d/%d   framed %d%% (need %d%%)   %.0f s') % (
            self.rung, self.trial, self.total_trials, round(100 * share),
            round(100 * run.level.need), max(0.0, run.level.seconds - run.t))
