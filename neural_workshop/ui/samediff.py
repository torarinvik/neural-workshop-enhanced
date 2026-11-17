# -*- coding: utf-8 -*-
"""Same or Different? on screen: the two things side by side (or one
after the other), or a speaker while they play.

For the agent boundary: port 0 says the same, 1 different.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import samediff as model
from ..i18n import _
from . import polish, taskoptions
from .showtask import ShowTask

PAPER = (248, 247, 242)


class SameDiff(ShowTask):
    """The same, or different -- in this one respect?"""

    instance: Optional['SameDiff'] = None

    TITLE = 'Same or Different?'
    TASK_ID = 'same_or_different'
    PREFIX = 'SAMEDIFF'
    CATEGORY = 'perception'
    FOOTNOTE = _('S: same   D: different   (or 1 / 2, or click)   '
                 'Esc: menu')

    def _read_options(self) -> None:
        super()._read_options()
        spec = getattr(taskoptions, self.PREFIX, None)
        self.guise = 'mixed'
        if spec is not None:
            opts = taskoptions.settings(spec)
            self.guise = str(opts.get(self.PREFIX + '_GUISE', 'mixed'))

    def _make(self):
        guise = getattr(self, 'guise', 'mixed')
        return model.deal(self.rung, rng=self.rng,
                          guise=None if guise == 'mixed' else guise)

    def _key(self, symbol: int, modifiers: int) -> None:
        pick = {key.S: 0, key.D: 1}.get(symbol)
        if pick is not None:
            self.choose(pick)
            return
        super()._key(symbol, modifiers)

    def _thing(self, th, cx, cy, r) -> None:
        if th.dots:
            for x, y, rr in th.dots:
                self.drawn.append(pyglet.shapes.Circle(
                    cx + x * r, cy + y * r, rr * r, color=th.hue,
                    batch=self.batch, group=self.body_group))
            return
        c, s = math.cos(th.turn), math.sin(th.turn)
        k = r * 0.62 * th.scale
        ox, oy = cx + th.x * r * 0.3, cy + th.y * r * 0.3
        pts = [(ox + (x * c - y * s) * k, oy + (x * s + y * c) * k)
               for x, y in th.outline]
        self.drawn.append(pyglet.shapes.Polygon(
            *pts, color=th.hue, batch=self.batch, group=self.body_group))

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        side = min(width / 2 * 0.9, height)
        for k, (th, (a, b)) in enumerate(((p.a, p.show_a), (p.b, p.show_b))):
            x = left + width / 2 + (-1.04 if k == 0 else 0.04) * side
            y = bottom + (height - side) / 2
            polish.card(self.drawn, self.batch, x, y, side, side, PAPER,
                        radius=14, group=self.card_group)
            if p.guise in model.SOUND:
                self._text(_('listen'), x + side / 2, y + side / 2,
                           side * 0.08, colour=(140, 140, 150, 255))
                continue
            if a <= t < b or self.phase == 'judged':
                self._thing(th, x + side / 2, y + side / 2, side / 2)
