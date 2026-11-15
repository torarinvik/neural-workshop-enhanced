# -*- coding: utf-8 -*-
"""Tuner on screen: an old wooden radio with a glowing dial.

A cabinet with a cloth speaker, a long lit dial window with a needle,
a signal meter and a big knob. While the sound first plays the dial is
dark and a card says to listen. Then the radio warms up. Drag the
needle or click along the dial to jump there, drag the knob, or hold
Left / Right (with Shift for fine tuning); Space locks on, R plays the
sound again. On the first rungs small lamps on the dial mark where the
stations are; nothing ever marks which one plays what.

For the agent boundary: ports 0 and 1 turn the dial down and up for
one step, 2 and 3 the same finely; 4 locks on; 5 plays the sound again. The
radio is heard as a stereo mix of the recordings on the agent's
audio channel, exactly as it plays.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import tuner as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .pointer import Pointer
from .tones import Tones

WOOD = (120, 72, 40)
GLOW = (255, 196, 110)


class Tuner(Pointer, Tones, ClockedTask):
    """Lock on to the station that plays the sound."""

    instance: Optional['Tuner'] = None

    TITLE = 'Tuner'
    TASK_ID = 'tuner'
    PREFIX = 'TUNER'
    CATEGORY = 'perception'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.SPACE: model.LOCK, key.R: model.REPLAY}
    FOOTNOTE = _('Drag or click the dial, or Left / Right (Shift: fine)   '
                 'Space: lock on   R: hear it again   Esc: menu')

    def __init__(self) -> None:
        self.parts = {}
        super().__init__()

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        self.message = _('Listen to the sound...')
        model.warm(run.radio)
        self._tones_stream(lambda t0, t1, run=run: model.mix(run, t0, t1),
                           run.end + 1.0)
        return ok

    # --- controls -----------------------------------------------------------

    def _held(self):
        k = self.keys
        fine = k[key.LSHIFT] or k[key.RSHIFT]
        on = set()
        if k[key.LEFT] or k[key.A]:
            on.add(model.FINE_DOWN if fine else model.DOWN)
        if k[key.RIGHT] or k[key.D]:
            on.add(model.FINE_UP if fine else model.UP)
        return on or None

    def _dial_at(self, x: float) -> Optional[float]:
        win = self.parts.get('dial')
        if win is None:
            return None
        x0, _y0, w, _h = win
        return max(0.0, min(model.DIAL, (x - x0) / w * model.DIAL))

    def _inside(self, name: str, x: float, y: float) -> bool:
        r = self.parts.get(name)
        return r is not None and r[0] <= x <= r[0] + r[2] and \
            r[1] <= y <= r[1] + r[3]

    def _click(self, x: float, y: float, button: int) -> None:
        if button == mouse.LEFT and self.run is not None and \
                self._inside('dial', x, y):
            self.run.dial = self._dial_at(x)
            self._redraw()
            return
        super()._click(x, y, button)

    def _drag(self, dx, dy, buttons, modifiers) -> None:
        run = self.run
        if not self.pointer:
            return
        x, y = self.pointer
        if self._inside('dial', x - dx, y - dy):
            run.dial = self._dial_at(x)
        elif self._inside('knob', x - dx, y - dy):
            fine = modifiers & pyglet.window.key.MOD_SHIFT
            run.dial = max(0.0, min(model.DIAL, run.dial + (dx + dy) *
                                    (0.02 if fine else 0.12)))

    def _tick(self) -> None:
        run = self.run
        if run is not None:
            if run.on() and self.message == _('Listen to the sound...'):
                self.message = _('Find the station playing it, then Space')
            if run.said:
                self.message, run.said = run.said, ''
        super()._tick()

    # --- drawing --------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        d, batch = self.drawn, self.batch
        W = min(width, height * 1.9)
        H = W / 1.9
        x0 = left + (width - W) / 2
        y0 = bottom + (height - H) / 2
        g0 = pyglet.graphics.Group(order=-14)
        g1 = pyglet.graphics.Group(order=-13)
        on = run.on()
        t = run.t
        # The cabinet.
        polish.card(d, batch, x0, y0, W, H, WOOD, radius=W * 0.05,
                    shade=(0, 0, 0, 90), group=polish.STAGE)
        polish.gradient(d, batch, x0 + W * 0.02, y0 + H * 0.03, W * 0.96,
                        H * 0.94, (110, 64, 34), (150, 94, 56), bands=14,
                        group=g0)
        for k in range(9):
            yy = y0 + H * (0.06 + 0.1 * k)
            d.append(pyglet.shapes.Line(x0 + W * 0.03, yy, x0 + W * 0.97,
                                        yy + math.sin(k * 1.7) * 3,
                                        thickness=1, color=(96, 56, 30, 120),
                                        batch=batch, group=g1))
        # The dial window.
        dx0, dy0, dw, dh = x0 + W * 0.07, y0 + H * 0.62, W * 0.86, H * 0.26
        self.parts['dial'] = (dx0, dy0, dw, dh)
        lamp = polish.mix((60, 50, 40), (250, 226, 170),
                          1.0 if on else 0.25 + 0.15 * math.sin(t * 4))
        polish.rounded(d, batch, dx0 - 5, dy0 - 5, dw + 10, dh + 10,
                       (200, 170, 110), radius=10, group=g1)
        polish.rounded(d, batch, dx0, dy0, dw, dh, lamp, radius=7,
                       group=self.card_group)
        for k in range(0, 101, 2):
            x = dx0 + dw * k / 100.0
            tall = 0.32 if k % 10 == 0 else 0.16
            d.append(pyglet.shapes.Line(x, dy0 + dh * 0.15, x,
                                        dy0 + dh * (0.15 + tall),
                                        thickness=2 if k % 10 == 0 else 1,
                                        color=(70, 50, 30), batch=batch,
                                        group=self.body_group))
            if k % 10 == 0:
                self._text('%d' % (88 + k // 5), x, dy0 + dh * 0.7,
                           max(7.0, dh * 0.13), colour=(70, 50, 30, 255))
        if run.level.lamps and on:
            for k in range(len(run.radio.stations)):
                x = dx0 + dw * run.where(k) / model.DIAL
                polish.glow(d, batch, x, dy0 + dh * 0.88, dh * 0.1,
                            (255, 140, 60), strength=200,
                            group=self.text_group)
        nx = dx0 + dw * run.dial / model.DIAL
        d.append(pyglet.shapes.Line(nx, dy0 + 3, nx, dy0 + dh - 3,
                                    thickness=4, color=(200, 40, 30),
                                    batch=batch, group=self.top_group))
        # The speaker cloth, pulsing with the signal.
        sig = run.signal()
        sx, sy, sr = x0 + W * 0.24, y0 + H * 0.3, H * 0.2
        d.append(pyglet.shapes.Circle(sx, sy, sr * 1.08, color=(90, 52, 28),
                                      batch=batch, group=g1))
        d.append(pyglet.shapes.Circle(sx, sy, sr, color=(196, 170, 130),
                                      batch=batch, group=self.card_group))
        throb = 0.02 * sig * math.sin(t * 30)
        for k in range(1, 6):
            d.append(pyglet.shapes.Arc(sx, sy, sr * (k / 6.0 + throb),
                                       thickness=2, color=(150, 120, 90),
                                       batch=batch, group=self.body_group))
        if not on:
            self._listen_card(sx, sy, sr)
        # The signal meter.
        mx, my, mr = x0 + W * 0.52, y0 + H * 0.2, H * 0.24
        polish.rounded(d, batch, mx - mr * 1.1, my - mr * 0.15, mr * 2.2,
                       mr * 1.35, (236, 222, 190), radius=8,
                       group=self.card_group)
        d.append(pyglet.shapes.Arc(mx, my, mr * 0.9, angle=108,
                                   start_angle=36, thickness=3,
                                   color=(80, 60, 40), batch=batch,
                                   group=self.body_group))
        a = math.pi * (0.8 - 0.6 * min(1.0, sig))
        d.append(pyglet.shapes.Line(mx, my, mx + math.cos(a) * mr * 0.95,
                                    my + math.sin(a) * mr * 0.95, thickness=3,
                                    color=(30, 30, 30), batch=batch,
                                    group=self.text_group))
        self._text(_('SIGNAL'), mx, my + mr * 1.05, max(7.0, mr * 0.12),
                   bold=True, colour=(80, 60, 40, 255))
        # The knob and the lock ring.
        kx, ky, kr = x0 + W * 0.8, y0 + H * 0.3, H * 0.17
        self.parts['knob'] = (kx - kr, ky - kr, 2 * kr, 2 * kr)
        d.append(pyglet.shapes.Circle(kx, ky - 3, kr, color=(40, 26, 16),
                                      batch=batch, group=g1))
        d.append(pyglet.shapes.Circle(kx, ky, kr, color=(70, 44, 26),
                                      batch=batch, group=self.card_group))
        for k in range(16):
            a = 2 * math.pi * k / 16
            d.append(pyglet.shapes.Line(kx + math.cos(a) * kr * 0.85,
                                        ky + math.sin(a) * kr * 0.85,
                                        kx + math.cos(a) * kr,
                                        ky + math.sin(a) * kr, thickness=2,
                                        color=(110, 76, 50), batch=batch,
                                        group=self.body_group))
        a = run.dial / model.DIAL * 2 * math.pi * 3
        d.append(pyglet.shapes.Line(kx, ky, kx + math.cos(a) * kr * 0.8,
                                    ky + math.sin(a) * kr * 0.8, thickness=4,
                                    color=(240, 220, 190), batch=batch,
                                    group=self.text_group))
        if run.lock_since is not None:
            share = min(1.0, (t - run.lock_since) / run.level.hold)
            d.append(pyglet.shapes.Arc(kx, ky, kr * 1.18, thickness=5,
                                       angle=360 * share,
                                       start_angle=90,
                                       color=(110, 240, 150), batch=batch,
                                       group=self.top_group))
        if run.result is not None and run.result[0]:
            polish.glow(d, batch, nx, dy0 + dh / 2, dh * 0.8, (120, 255, 150),
                        strength=140, group=self.top_group)
        # The clock.
        share = max(0.0, (run.end - t) / run.level.seconds) if on else 1.0
        if share > 0.01:
            polish.rounded(d, batch, x0 + W * 0.07, y0 + H * 0.93,
                           W * 0.86 *
                           min(1.0, share), H * 0.025,
                           polish.mix((236, 80, 64), (110, 220, 140),
                                      min(1.0, share * 1.5)), radius=3,
                           group=self.body_group)

    def _listen_card(self, x, y, r) -> None:
        d, batch = self.drawn, self.batch
        polish.glow(d, batch, x, y, r * 1.3, GLOW, strength=160,
                    group=self.text_group)
        t = self.run.t
        for k in range(3):
            rr = r * (0.3 + 0.25 * k + 0.1 * math.sin(t * 6 - k))
            d.append(pyglet.shapes.Arc(x, y, rr, thickness=3,
                                       color=(255, 255, 255, 200),
                                       batch=batch, group=self.top_group))
        self._text(_('Listen'), x, y - r * 1.25, max(9.0, r * 0.18),
                   bold=True, colour=(255, 240, 210, 255))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        kind = (_('recordings') if self.run.radio.heard.bank == 'esc50'
                else _('tunes (fetch esc50 for recordings)'))
        return _('rung %d  %d/%d   %d stations   %s') % (
            self.rung, self.trial, self.total_trials,
            len(self.run.radio.stations), kind)
