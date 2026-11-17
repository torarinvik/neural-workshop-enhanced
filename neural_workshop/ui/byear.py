# -*- coding: utf-8 -*-
"""By Ear on screen: one octave of a keyboard, and nothing else to see.

The keys do not light while the tune plays. Play it back with the
mouse, or on the computer keys laid out like a keyboard: A W S E D F T
G Y H U J K from C to C. On the rungs where the tune is played back
from another key, that first key is lit.

For the agent boundary: ports 0-12 press the keys from C to C.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import byear as model
from ..i18n import _
from .livetask import LiveTask

KEYMAP = (key.A, key.W, key.S, key.E, key.D, key.F, key.T, key.G, key.Y,
          key.H, key.U, key.J, key.K)
BLACK = (1, 3, 6, 8, 10)


class ByEar(LiveTask):
    """Hear the tune, then play it back."""

    instance: Optional['ByEar'] = None

    TITLE = 'By Ear'
    TASK_ID = 'by_ear'
    PREFIX = 'EAR'
    CATEGORY = 'perception'
    MODEL = model
    EVENT_KEYS = {k: n for n, k in enumerate(KEYMAP)}
    FOOTNOTE = _('Click the keys, or A W S E D F T G Y H U J K   Esc: menu')

    def _tick(self) -> None:
        run = self.run
        if run is not None:
            self.message = (_('Listen...') if run.listening() else
                            _('Play it back: %d of %d') % (
                                run.done, len(run.tune.want)))
        super()._tick()

    def _keys(self, left, bottom, width, height):
        """Each key's rectangle: (x, y, w, h, black)."""
        n_white = len(model.WHITE)
        kw = min(width * 0.9 / n_white, 110.0)
        kh = min(height * 0.7, kw * 4.2)
        x0 = left + (width - kw * n_white) / 2
        y0 = bottom + (height - kh) / 2
        out = {}
        for i, k in enumerate(model.WHITE):
            out[k] = (x0 + i * kw, y0, kw, kh, False)
        for k in BLACK:
            i = model.WHITE.index(k - 1)
            out[k] = (x0 + (i + 1) * kw - kw * 0.3, y0 + kh * 0.38, kw * 0.6,
                      kh * 0.62, True)
        return out

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height)
        rects = self._keys(left, bottom, width, height)
        recent = {k for t, k, ok in run.pressed if run.t - t < 0.25}
        bad = {k for t, k, ok in run.pressed if not ok}
        for black in (False, True):
            g = self.layer()
            for k, (x, y, w, h, b) in rects.items():
                if b != black:
                    continue
                live = k in run.level.keys
                if b:
                    c = (40, 40, 50) if live else (90, 90, 100)
                else:
                    c = (250, 250, 245) if live else (170, 170, 175)
                if run.tune.lit == k and not run.listening():
                    c = (250, 210, 90)
                if k in recent:
                    c = (130, 200, 250)
                if k in bad and run.result is not None:
                    c = (230, 90, 80)
                self.rect(x, y, w, h, (20, 20, 26), g)
                self.rect(x + 2, y + 2, w - 4, h - 4, c, g)
                if live:
                    self.hits.append((x, y, w, h,
                                      lambda k=k: self.steer(k)))
        # black keys sit over white: the last hit wins, so put them first
        self.hits.sort(key=lambda h: h[2])
        done = len(run.tune.want)
        for i in range(done):
            c = (110, 220, 140) if i < run.done else (90, 96, 120)
            self.disc((left + width / 2 + (i - (done - 1) / 2) * 22,
                       bottom + height - 24), 7, c, self.layer())

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   %d notes') % (
            self.rung, self.trial, self.total_trials,
            len(self.run.tune.want))
