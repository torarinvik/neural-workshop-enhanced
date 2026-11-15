# -*- coding: utf-8 -*-
"""Hold It on screen: a great glass bulb on a brass stand.

The bulb lights (and hums) for the time to remember; a second bulb
beside it for the two-lamp rungs. On your turn the bulb lights again
while the key is held. Higher up a wall clock ticks at the wrong speed.
After the verdict, two bars compare the time asked for with the time
held.

For the agent boundary: port 0 holds, for the step it is sent in --
send it every step to keep holding; stop sending it to let go.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import holdit as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .tones import Tones, note, patch


class HoldIt(Tones, ClockedTask):
    """Hold the key exactly as long as asked."""

    instance: Optional['HoldIt'] = None

    TITLE = 'Hold It'
    TASK_ID = 'hold_it'
    PREFIX = 'HOLDIT'
    CATEGORY = 'self_control'
    FEEDBACK = 3.0
    MODEL = model
    SUBSTEP = 1 / 240.0
    FOOTNOTE = _('watch the lamp, then hold Space just as long   Esc: menu')

    def _held(self) -> Optional[int]:
        return model.HOLD if self.keys[key.SPACE] else None

    def _deal(self) -> bool:
        ok = super()._deal()
        ask = self.run.ask
        self.message = {
            'copy': _('Remember how long it shines; then hold that long'),
            'scale': (_('Then hold HALF as long') if ask.factor < 1
                      else _('Then hold TWICE as long')),
            'sum': _('Two lamps: then hold as long as both together'),
        }[ask.kind]
        notes = [note(a, b - a, 330.0 + 110 * k, pan=-0.3 + 0.6 * k,
                      gain=0.5, voice=0, seed=k)
                 for k, (a, b) in enumerate(ask.lamps)]
        if ask.tick:
            t = 0.3
            while t < ask.turn + model.WAIT + 6:
                notes.append(note(t, 0.04, 1400.0, pan=0.6, gain=0.35,
                                  voice=1, seed=int(t * 100)))
                t += ask.tick
        self._tones_start(notes, [patch('organ'), patch('wood')],
                          ask.turn + model.WAIT + 6)
        return ok

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        d, batch = self.drawn, self.batch
        ask = run.ask
        t = run.t
        polish.card(d, batch, left, bottom, width, height, (24, 26, 40),
                    radius=16, shade=(0, 0, 0, 60), group=self.back_group)
        polish.gradient(d, batch, left + 4, bottom + 4, width - 8,
                        height - 8, (20, 22, 34), (46, 40, 70), bands=16,
                        group=self.back_group)
        n = len(ask.lamps)
        r = min(width, height) * 0.13
        for k in range(n):
            cx = left + width * (0.5 if n == 1 else 0.38 + 0.24 * k)
            cy = bottom + height * 0.56
            a, b = ask.lamps[k]
            on = a <= t < b or (run.holding and k == 0) or \
                (run.holding and n == 2 and k == 1)
            colour = (255, 214, 120) if k == 0 else (140, 220, 255)
            if on:
                polish.glow(d, batch, cx, cy, r * 3.0, colour,
                            strength=170, group=self.card_group)
            d.append(pyglet.shapes.Circle(cx, cy, r,
                                          color=colour if on else
                                          (70, 70, 90), batch=batch,
                                          group=self.body_group))
            d.append(pyglet.shapes.Circle(cx - r * 0.35, cy + r * 0.35,
                                          r * 0.22,
                                          color=(255, 255, 255, 120 if on
                                                 else 50),
                                          batch=batch,
                                          group=self.text_group))
            d.append(pyglet.shapes.Rectangle(cx - r * 0.4, cy - r * 1.6,
                                             r * 0.8, r * 0.7,
                                             color=(170, 140, 70),
                                             batch=batch,
                                             group=self.body_group))
            for j in range(3):
                d.append(pyglet.shapes.Line(
                    cx - r * 0.4, cy - r * (1.0 + 0.2 * j), cx + r * 0.4,
                    cy - r * (1.0 + 0.2 * j), thickness=2,
                    color=(120, 96, 40), batch=batch, group=self.text_group))
        if ask.tick:
            self._clock(left + width * 0.86, bottom + height * 0.72,
                        min(width, height) * 0.09, t, ask.tick)
        if run.your_turn() and run.result is None:
            words = _('Hold now') if run.down is None else _('holding...')
            self._text(words, left + width / 2, bottom + height * 0.2, 20,
                       bold=True, colour=(255, 240, 200, 240))
        if run.result is not None and run.held is not None:
            self._bars(left, bottom, width, height, ask.target, run.held)

    def _clock(self, cx, cy, r, t, tick) -> None:
        d, batch = self.drawn, self.batch
        d.append(pyglet.shapes.Circle(cx, cy, r, color=(236, 230, 214),
                                      batch=batch, group=self.body_group))
        d.append(pyglet.shapes.Arc(cx, cy, r, thickness=3,
                                   color=(90, 70, 50), batch=batch,
                                   group=self.text_group))
        steps = int(t / tick)
        a = math.pi / 2 - steps * 2 * math.pi / 60
        d.append(pyglet.shapes.Line(cx, cy, cx + math.cos(a) * r * 0.85,
                                    cy + math.sin(a) * r * 0.85,
                                    thickness=2, color=(200, 40, 40),
                                    batch=batch, group=self.top_group))

    def _bars(self, left, bottom, width, height, target, held) -> None:
        d, batch = self.drawn, self.batch
        most = max(target, held) * 1.15
        bw = width * 0.6
        x = left + width * 0.2
        for k, (value, colour, words) in enumerate((
                (target, (120, 220, 150), _('asked')),
                (held, (255, 200, 110), _('held')))):
            y = bottom + height * (0.16 - 0.08 * k)
            polish.rounded(d, batch, x, y, bw, 14, (60, 60, 80), radius=7,
                           group=self.card_group)
            polish.rounded(d, batch, x, y, max(14.0, bw * value / most), 14,
                           colour, radius=7, group=self.body_group)
            self._text('%s %.2f s' % (words, value), x - 10, y + 7, 11,
                       anchor='right', colour=(230, 230, 240, 230))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   within %d%%') % (
            self.rung, self.trial, self.total_trials,
            round(self.run.level.margin * 100))
