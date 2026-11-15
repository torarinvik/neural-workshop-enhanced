# -*- coding: utf-8 -*-
"""Time It on screen: a ball, a lane, and a striped screen to hide it.

A bright ball rolls along a lane (or flies in an arc) and goes behind a
tall striped screen with a glowing mark on it. Press as it passes the
mark. A soft rolling hum follows the ball while it can be seen, and
stops when it is hidden. After the press the screen turns see-through:
a ghost shows where the ball was at the press, the real ball where it
was at the mark.

For the agent boundary: port 0 presses.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import timeit as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .tones import Tones, note, patch


class TimeIt(Tones, ClockedTask):
    """Press as the hidden ball passes the mark."""

    instance: Optional['TimeIt'] = None

    TITLE = 'Time It'
    TASK_ID = 'time_it'
    PREFIX = 'TIMEIT'
    CATEGORY = 'perception'
    FEEDBACK = 3.0
    MODEL = model
    SUBSTEP = 1 / 240.0
    EVENT_KEYS = {key.SPACE: model.PRESS}
    FOOTNOTE = _('Space: press when the hidden ball is at the mark   '
                 'Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        shot = self.run.shot
        self.message = {
            'roll': _('Press as it passes the mark'),
            'slow': _('It is slowing -- press as it passes the mark'),
            'bounce': _('It bounces off the wall -- press as it comes back '
                        'to the mark'),
            'throw': _('Press as it lands on the mark'),
        }[shot.kind]
        # A rolling hum while the ball is in view.
        notes, t = [], 0.0
        while True:
            x, _y = model.where(shot, t)
            if x >= shot.screen[0] or t > shot.when:
                break
            notes.append(note(t, 0.1, 110.0, pan=(x / model.W) * 2 - 1,
                              gain=0.35, voice=0, seed=int(t * 100)))
            t += 0.1
        self._tones_start(notes, [patch('pad')], shot.when + 1.0)
        return ok

    def _frame(self):
        left, bottom, width, height = self._area()
        s = min(width / model.W, height / model.H)
        return left + (width - model.W * s) / 2, bottom + (
            height - model.H * s) / 2, s

    def _at(self, x, y):
        x0, y0, s = self._frame()
        return x0 + x * s, y0 + y * s

    def _build_scenery(self) -> None:
        x0, y0, s = self._frame()
        out, batch = self.scenery, self.batch
        W, H = model.W * s, model.H * s
        g0 = pyglet.graphics.Group(order=-14)
        polish.card(out, batch, x0 - 6, y0 - 6, W + 12, H + 12,
                    (30, 40, 70), radius=14, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        polish.gradient(out, batch, x0, y0, W, H, (120, 190, 240),
                        (40, 80, 160), bands=20, group=g0)
        gy = model.GROUND * s
        polish.gradient(out, batch, x0, y0, W, gy - 0.8 * s, (60, 140, 70),
                        (110, 190, 100), bands=5, group=g0)
        for k in range(int(model.W / 4)):
            out.append(pyglet.shapes.Line(
                x0 + k * 4 * s, y0 + gy - 0.8 * s, x0 + k * 4 * s + 2 * s,
                y0 + gy - 0.8 * s, thickness=2, color=(240, 240, 230),
                batch=batch, group=g0))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        x0, y0, s = self._frame()
        self._scenery_fresh(self._frame())
        d, batch = self.drawn, self.batch
        shot = run.shot
        t = run.t
        r = 1.6 * s
        judged = run.result is not None
        # The bounce wall, behind the screen.
        if shot.kind == 'bounce':
            wx, wy = self._at(shot.wall, model.GROUND - 0.8)
            d.append(pyglet.shapes.Rectangle(wx, wy, 1.2 * s, 9 * s,
                                             color=(120, 80, 60),
                                             batch=batch,
                                             group=self.card_group))
        # The ball, then the screen over it.
        bx, by = model.where(shot, t if not judged else shot.when)
        px, py = self._at(bx, by + 1.6)
        spin = -bx / 1.6
        d.append(pyglet.shapes.Circle(px, py, r, color=(250, 90, 80),
                                      batch=batch, group=self.body_group))
        d.append(pyglet.shapes.Line(px, py, px + math.cos(spin) * r,
                                    py + math.sin(spin) * r, thickness=3,
                                    color=(255, 220, 200), batch=batch,
                                    group=self.text_group))
        if judged and run.pressed is not None:
            gx, gy = model.where(shot, run.pressed)
            qx, qy = self._at(gx, gy + 1.6)
            d.append(pyglet.shapes.Arc(qx, qy, r, thickness=3,
                                       color=(255, 255, 255, 220),
                                       batch=batch, group=self.top_group))
        sx, sy = self._at(shot.screen[0], 0)
        sw = (shot.screen[1] - shot.screen[0]) * s
        sh = model.H * s
        alpha = 110 if judged else 255
        stripes = max(3, int(sw / (3 * s)))
        for k in range(stripes):
            colour = (250, 210, 70) if k % 2 else (60, 70, 120)
            d.append(pyglet.shapes.Rectangle(
                sx + sw * k / stripes, sy, sw / stripes + 1, sh,
                color=colour + (alpha,), batch=batch,
                group=pyglet.graphics.Group(order=6)))
        mx, _my = self._at(shot.mark, 0)
        top = pyglet.graphics.Group(order=7)
        polish.glow(d, batch, mx, sy + sh * 0.5, 4 * s, (255, 255, 255),
                    strength=60, group=top)
        d.append(pyglet.shapes.Line(mx, sy, mx, sy + sh, thickness=4,
                                    color=(255, 255, 255), batch=batch,
                                    group=top))
        d.append(pyglet.shapes.Triangle(mx - 2 * s, sy + sh, mx + 2 * s,
                                        sy + sh, mx, sy + sh - 3 * s,
                                        color=(255, 80, 120), batch=batch,
                                        group=top))
        if run.pressed is not None:
            flash = max(0.0, 1.0 - (t - run.pressed) / 0.3)
            if flash:
                polish.glow(d, batch, mx, sy + sh * 0.5, 10 * s,
                            (255, 255, 200), strength=int(150 * flash),
                            group=top)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   window +-%d ms') % (
            self.rung, self.trial, self.total_trials,
            round(self.run.level.window * 1000))
