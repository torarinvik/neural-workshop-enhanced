# -*- coding: utf-8 -*-
"""Piano Tuner on screen: the strings of a piano seen from above, a
tuning hammer on one pin, and nothing that shows the pitch.

Up / Down turn the pin quickly, with Shift slowly; or drag up and down
anywhere (slowly). Enter or Space says the string is in tune.

For the agent boundary: ports 0 / 1 turn the pin up / down quickly, 2
/ 3 slowly; port 4 says done.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from pyglet.window import key, mouse

from .. import pianotuner as model
from ..i18n import _
from .livetask import LiveTask


class PianoTuner(LiveTask):
    """Tune the string until it stops beating."""

    instance: Optional['PianoTuner'] = None

    TITLE = 'Piano Tuner'
    TASK_ID = 'piano_tuner'
    PREFIX = 'TUNE'
    CATEGORY = 'perception'
    MODEL = model
    BACK = (52, 36, 28)
    EVENT_KEYS = {key.RETURN: model.DONE, key.ENTER: model.DONE}
    FOOTNOTE = _('Up / Down: turn the pin (Shift: slowly)   '
                 'Enter: in tune   Esc: menu')

    def _held(self):
        k = self.keys
        fine = k[key.LSHIFT] or k[key.RSHIFT]
        if k[key.UP] or k[key.W]:
            return model.UP_FINE if fine else model.UP
        if k[key.DOWN] or k[key.S]:
            return model.DOWN_FINE if fine else model.DOWN
        return None

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)
        run = self.run
        if run is not None and self.phase == self.PLAY and \
                buttons & mouse.LEFT and run.result is None:
            run.pitch *= 2 ** (0.4 * dy / 1200.0)

    def _key(self, symbol, modifiers) -> None:
        if symbol == key.SPACE:
            self.steer(model.DONE)
        else:
            super()._key(symbol, modifiers)

    def _tick(self) -> None:
        run = self.run
        if run is not None:
            iv = run.job.plan[run.k][0]
            self.message = _('String %d of %d: tune it %s') % (
                run.k + 1, run.level.strings, model.NAMES[iv])
        super()._tick()

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self.frame(left, bottom, width, height)
        g = self.layer()
        # the iron frame and the felt
        self.rect(left + 30, bottom + 30, width - 60, height - 60,
                  (150, 120, 60), g)
        self.rect(left + 50, bottom + height - 120, width - 100, 40,
                  (120, 30, 40), g)
        g = self.layer()
        n = 12
        top = bottom + height - 70
        low = bottom + 60
        for i in range(n):
            x = left + 90 + i * (width - 180) / (n - 1)
            here = i == 5 + run.k
            col = (250, 240, 200) if here else (200, 190, 170)
            self.line((x, low), (x, top), 3 if here else 2, col, g)
            self.disc((x, top - 6), 7, (90, 90, 96), g)
        g = self.layer()
        x = left + 90 + (5 + run.k) * (width - 180) / (n - 1)
        cx, cy = x, top - 6
        a = math.radians(run.pin())
        r = 46
        self.disc((cx, cy), 18, (70, 70, 80), g)
        self.line((cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a)), 10,
                  (60, 50, 40), g)
        self.disc((cx + r * math.cos(a), cy + r * math.sin(a)), 12,
                  (90, 70, 50), g)
        for i, f in enumerate(run.tuned):
            xx = left + 90 + (5 + i) * (width - 180) / (n - 1)
            self.disc((xx, low - 20), 6, (110, 220, 140), self.layer())

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   within %.1f cents') % (
            self.rung, self.trial, self.total_trials, self.run.level.tol)
