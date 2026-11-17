# -*- coding: utf-8 -*-
"""Which Block? on screen: the blocks, the machine and its lamp, the
tries so far.

For the agent boundary: ports 0-7 put block 1-8 on the machine or take
it off; port 8 runs the machine; ports 9-16 name block 1-8.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import blicket as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint, polish
from .rungtask import RungTask

LIT = (255, 210, 60)
DARK = (70, 70, 80)


class Blicket(RungTask):
    """Try blocks on the machine; say which makes it go."""

    instance: Optional['Blicket'] = None

    TITLE = 'Which Block?'
    TASK_ID = 'which_block'
    PREFIX = 'BLICKET'
    CATEGORY = 'reasoning'
    FEEDBACK = 2.0
    FOOTNOTE = _('1-8 or click a block: on / off   Space: run   '
                 'Shift+1-8 or click its name tag: that one   Esc: menu')

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.run = None

    def _deal(self) -> bool:
        self.run = model.Run(model.deal(self.rung, rng=self.rng))
        self.message = (_('Which two blocks make the machine go together?')
                        if self.run.m.level.pair else
                        _('Which block makes the machine go?'))
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
        if symbol == key.SPACE:
            self.steer(model.RUN)
        elif key._1 <= symbol <= key._8:
            k = symbol - key._1
            self.steer(model.NAME + k if modifiers & key.MOD_SHIFT else k)

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   tries left %d') % (
            self.rung, self.trial, self.total_trials, self.run.left)

    def _block(self, k, x, y, s, faint=False) -> None:
        m = self.run.m
        polish.rounded(self.drawn, self.batch, x, y, s, s,
                       (236, 232, 222) if not faint else (246, 244, 240),
                       radius=s * 0.12, group=self.card_group)
        glyphpaint.glyph(self, m.look, m.blocks[k], x, y, s, s)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        m = run.m
        n = m.level.blocks
        # The tries so far, along the top: blocks on, and the lamp.
        hist = run.seen[-8:]
        rows = len(hist)
        rh = min(height * 0.42 / max(1, rows), height * 0.07)
        top = bottom + height
        self._text(_('Tries so far'), left + width * 0.02, top - 4,
                   calc_fontsize(12), anchor='left', anchor_y='top',
                   bold=True)
        for i, (on, lit) in enumerate(hist):
            y = top - (i + 1) * rh - 18
            for k in range(n):
                x = left + width * 0.02 + k * rh * 1.1
                if k in on:
                    self._block(k, x, y, rh * 0.95)
                else:
                    polish.rounded(self.drawn, self.batch, x, y, rh * 0.95,
                                   rh * 0.95, (244, 244, 246),
                                   radius=4, group=self.card_group)
            self.drawn.append(pyglet.shapes.Circle(
                left + width * 0.02 + n * rh * 1.1 + rh, y + rh / 2,
                rh * 0.38, color=LIT if lit else DARK, batch=self.batch,
                group=self.top_group))
        # The machine, on the right.
        mx, my = left + width * 0.55, bottom + height * 0.32
        mw, mh = width * 0.4, height * 0.26
        polish.card(self.drawn, self.batch, mx, my, mw, mh, (90, 110, 140),
                    radius=12, group=self.card_group)
        lamp = LIT if run.lit else DARK
        self.drawn.append(pyglet.shapes.Circle(
            mx + mw / 2, my + mh + height * 0.08, height * 0.06,
            color=lamp, batch=self.batch, group=self.top_group))
        on = sorted(run.on)
        s = min(mw / max(1, len(on) + 1), mh * 0.7)
        for i, k in enumerate(on):
            self._block(k, mx + mw * 0.05 + i * s * 1.05, my + mh * 0.15,
                        s * 0.95)
        bx, bw = mx + mw * 0.3, mw * 0.4
        polish.button(self.drawn, self.batch, bx, my - height * 0.1, bw,
                      height * 0.08, (240, 200, 80) if run.left > 0
                      else (180, 180, 180), radius=10, group=self.card_group)
        self._text(_('Run'), bx + bw / 2, my - height * 0.06,
                   calc_fontsize(14), bold=True, colour=(30, 30, 30, 255))
        self.hits.append((bx, my - height * 0.1, bw, height * 0.08,
                          lambda: self.steer(model.RUN)))
        # The blocks, along the bottom: click to put on or take off; the
        # tag below names one.
        s = min(width * 0.5 / n * 0.85, height * 0.16)
        for k in range(n):
            x = left + width * 0.02 + k * s * 1.15
            y = bottom + height * 0.08
            self._block(k, x, y, s, faint=k in run.on)
            self.hits.append((x, y, s, s, lambda c=k: self.steer(c)))
            named = k in run.named
            polish.rounded(self.drawn, self.batch, x, bottom, s,
                           height * 0.06, (230, 200, 120) if named
                           else (220, 224, 232), radius=6,
                           group=self.card_group)
            self._text(_('this'), x + s / 2, bottom + height * 0.03,
                       calc_fontsize(11), bold=True)
            self.hits.append((x, bottom, s, height * 0.06,
                              lambda c=k: self.steer(model.NAME + c)))
