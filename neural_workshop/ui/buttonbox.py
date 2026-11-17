# -*- coding: utf-8 -*-
"""Button Box on screen: the figure, the target, the buttons.

For the agent boundary: ports 0-11 press buttons 1-12 (those beyond
the trial's buttons do nothing); port 12 resets the figure.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import buttonbox as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint, polish
from .rungtask import RungTask


class ButtonBox(RungTask):
    """Press to find out; match the target."""

    instance: Optional['ButtonBox'] = None

    TITLE = 'Button Box'
    TASK_ID = 'button_box'
    PREFIX = 'BUTTONBOX'
    CATEGORY = 'reasoning'
    FEEDBACK = 1.5
    FOOTNOTE = _('click a button or press 1-9, 0, -, =   R: reset   '
                 'Esc: menu')
    KEYS = (key._1, key._2, key._3, key._4, key._5, key._6, key._7, key._8,
            key._9, key._0, key.MINUS, key.EQUAL)

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.run = None

    def _deal(self) -> bool:
        self.run = model.Run(model.deal(self.rung, rng=self.rng))
        self.message = _('Make the figure match the target')
        return True

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY or self.run is None:
            return
        self.run.act(port)
        if self.run.result is not None:
            self._judge(*self.run.result)
        else:
            self._redraw()

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol == key.R:
            self.steer(model.RESET)
        elif symbol in self.KEYS:
            self.steer(self.KEYS.index(symbol))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   presses left %d') % (
            self.rung, self.trial, self.total_trials, max(0, self.run.left))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        box = run.box
        lk = box.look
        top = height * 0.62
        s = min(top * 0.95, width * 0.36)
        y = bottom + height - s
        for k, (state, words) in enumerate(((run.state, _('Now')),
                                            (box.target, _('Target')))):
            x = left + width / 2 + (-1.1 if k == 0 else 0.1) * s
            glyphpaint.panel(self, lk, x, y, s, s,
                             paper=(255, 255, 252) if k == 0
                             else (236, 240, 232))
            glyphpaint.glyph(self, lk, model.glyph(state), x, y, s, s)
            self._text(words, x + s / 2, y - 14, calc_fontsize(13), bold=True)
        n = len(box.buttons)
        bw = min(width / (n + 2) * 0.85, height * 0.18)
        gap = (width - bw * (n + 1)) / (n + 2)
        by = bottom + height * 0.04
        for k in range(n + 1):
            x = left + gap + k * (bw + gap)
            if k < n:
                hue = box.hues[k]
                pressed = run.last == k
                port = k
                words = str(k + 1) if k < 9 else '0-='[k - 9]
            else:
                hue, pressed, port, words = (200, 200, 205), \
                    run.last == model.RESET, model.RESET, _('Reset')
            polish.button(self.drawn, self.batch, x, by, bw, bw * 0.8, hue,
                          radius=bw * 0.18, pressed=pressed,
                          group=self.card_group)
            self._text(words, x + bw / 2, by + bw * 0.42,
                       calc_fontsize(13 if k == n else 16), bold=True,
                       colour=(30, 30, 40, 255))
            self.hits.append((x, by, bw, bw * 0.8,
                              lambda p=port: self.steer(p)))
