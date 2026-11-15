# -*- coding: utf-8 -*-
"""The screen for tasks played with a drawn pointer and the keys.

The model's screen is 1000 by 640 units; this fits it into the playing
area, keeps the model's pointer under the mouse, turns mouse presses
and releases into the same press and release an agent's ports send, and
draws the pointer, so the picture is the same whoever is playing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import pyglet
from pyglet.window import mouse

from .. import hand
from .. import state
from . import polish
from .clocked import ClockedTask
from .dronehoops import clip_line, clip_poly
from .tones import Tones, patch

Pt = Tuple[float, float]
SCREEN = (0.0, 0.0, hand.W, hand.H)


class HandTask(Tones, ClockedTask):
    """A clocked task with a pointer."""

    BACK = (28, 30, 44)
    #: Whether the bar along the bottom shows the time left.
    TIME_BAR = True

    def __init__(self) -> None:
        self.fit = (0.0, 0.0, 1.0)
        super().__init__()
        state.window.push_handlers(self.on_mouse_motion, self.on_mouse_drag,
                                   self.on_mouse_release)

    def close(self) -> None:
        if type(self).instance is self:
            try:
                state.window.remove_handlers(self.on_mouse_motion,
                                             self.on_mouse_drag,
                                             self.on_mouse_release)
            except Exception:
                pass
        super().close()

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        self._tones_live(run.notes, [patch(n, k + 1) for k, n in
                                     enumerate(self.MODEL.PATCHES)],
                         run.end + 2.0)
        return ok

    # --- the pointer -------------------------------------------------------------

    def _fit(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        s = min(width / hand.W, height / hand.H)
        self.fit = (left + (width - hand.W * s) / 2,
                    bottom + (height - hand.H * s) / 2, s)
        return self.fit

    def px(self, x: float, y: float) -> Pt:
        ox, oy, s = self.fit
        return ox + x * s, oy + y * s

    def _point(self, x: float, y: float) -> bool:
        if self.phase != self.PLAY or self.run is None:
            return False
        ox, oy, s = self._fit()
        self.run.hand.to((x - ox) / s, (y - oy) / s)
        return True

    def on_mouse_motion(self, x, y, dx, dy):
        self._point(x, y)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._point(x, y)

    def on_mouse_release(self, x, y, button, modifiers):
        if button == mouse.LEFT and self._point(x, y):
            self.MODEL.act(self.run, hand.RELEASE)

    def _click(self, x: float, y: float, button: int) -> None:
        if button == mouse.LEFT and self._point(x, y):
            self.MODEL.act(self.run, hand.PRESS)

    # --- drawing -------------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        ox, oy, s = self._fit()
        d, batch = self.drawn, self.batch
        polish.card(d, batch, ox - 4, oy - 4, hand.W * s + 8, hand.H * s + 8,
                    self.BACK, radius=14, shade=(0, 0, 0, 60),
                    group=polish.STAGE)
        self._scene(run, s)
        top = pyglet.graphics.Group(order=195)
        share = max(0.0, (run.end - run.t) / run.end)
        if share > 0.005 and self.TIME_BAR:
            d.append(pyglet.shapes.Rectangle(
                ox + 10 * s, oy + 6 * s, (hand.W - 20) * s * share, 6 * s,
                color=polish.mix((236, 80, 64), (110, 220, 140),
                                 min(1.0, share * 1.6)),
                batch=batch, group=top))
        # The pointer: an arrow, filled while the button is down.
        x, y = self.px(run.hand.x, run.hand.y)
        k = 16 * s
        tip = pyglet.graphics.Group(order=199)
        under = pyglet.graphics.Group(order=198)
        d.append(pyglet.shapes.Polygon(
            (x - 2 * s, y + 3 * s), (x - 2 * s, y - 1.5 * k),
            (x + 0.42 * k, y - 1.05 * k), (x + 1.15 * k, y - 1.0 * k),
            color=(20, 20, 30), batch=batch, group=under))
        d.append(pyglet.shapes.Polygon(
            (x, y), (x, y - 1.25 * k), (x + 0.36 * k, y - 0.9 * k),
            (x + 0.9 * k, y - 0.9 * k),
            color=(255, 210, 70) if run.hand.down else (255, 255, 255),
            batch=batch, group=tip))

    def _scene(self, run, s: float) -> None:
        raise NotImplementedError

    # --- helpers for scenes ----------------------------------------------------------

    def poly(self, pts: Sequence[Optional[Sequence[float]]], colour,
             group) -> None:
        """A filled convex polygon through screen-unit points."""
        if len(pts) < 3 or any(p is None for p in pts):
            return
        pts = clip_poly([(p[0], p[1]) for p in pts], SCREEN)
        if len(pts) < 3:
            return
        self.drawn.append(pyglet.shapes.Polygon(
            *[self.px(p[0], p[1]) for p in pts], color=colour,
            batch=self.batch, group=group))

    def line(self, a, b, thick: float, colour, group) -> None:
        if a is None or b is None:
            return
        cut = clip_line((a[0], a[1]), (b[0], b[1]), SCREEN)
        if cut is None:
            return
        a, b = cut
        ax, ay = self.px(a[0], a[1])
        bx, by = self.px(b[0], b[1])
        self.drawn.append(pyglet.shapes.Line(
            ax, ay, bx, by, thickness=max(1.0, thick * self.fit[2]),
            color=colour, batch=self.batch, group=group))

    def disc(self, p, r: float, colour, group) -> None:
        if p is None:
            return
        x, y = self.px(p[0], p[1])
        self.drawn.append(pyglet.shapes.Circle(
            x, y, max(1.0, r * self.fit[2]), color=colour, batch=self.batch,
            group=group))

    def rect(self, x, y, w, h, colour, group) -> None:
        ax, ay = self.px(x, y)
        s = self.fit[2]
        self.drawn.append(pyglet.shapes.Rectangle(
            ax, ay, w * s, h * s, color=colour, batch=self.batch,
            group=group))

    def words(self, text: str, x: float, y: float, size: float, group=None,
              **kw):
        ax, ay = self.px(x, y)
        if 'width' in kw:
            kw['width'] = kw['width'] * self.fit[2]
        return self._text(text, ax, ay, size * self.fit[2], group=group,
                          **kw)
