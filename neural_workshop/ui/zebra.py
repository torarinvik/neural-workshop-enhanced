# -*- coding: utf-8 -*-
"""Who Lives Where? on screen: picture clues, and the houses to pick.

For the agent boundary: port k picks house k (numbered from the left).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

import pyglet

from .. import shapekit as G
from .. import zebra as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint, polish
from .spacetask import ChoiceTask

SIGNS = {model.SAME: '=', model.NOT: '≠', model.LEFT: '|',
         model.BEFORE: '…', model.NEXT: '↔'}
LETTERS = 'ABCDEFGH'
FLAGS = ((200, 40, 40), (40, 90, 200), (240, 200, 30), (40, 150, 70),
         (140, 60, 170), (240, 130, 30), (30, 170, 180), (120, 120, 120))


class Zebra(ChoiceTask):
    """Which house has it?"""

    instance: Optional['Zebra'] = None

    TITLE = 'Who Lives Where?'
    TASK_ID = 'who_lives_where'
    PREFIX = 'ZEBRA'
    CATEGORY = 'reasoning'
    BUTTONS = 0
    FOOTNOTE = _('click the house or press its number   Esc: menu')

    def _make(self):
        p = model.deal(self.rung, rng=self.rng)
        draw = random.Random(p.seed)
        self.look = G.look(draw, shapes=8, colours=6)
        self.flags = draw.sample(FLAGS, len(FLAGS))
        return p

    def _thing(self, thing, x, y, s) -> None:
        """One thing's picture in an s-by-s box."""
        kind, v = thing
        lk = self.look
        if kind == 0:
            polish.rounded(self.drawn, self.batch, x + s * 0.1, y + s * 0.1,
                           s * 0.8, s * 0.8, lk.colours[v % len(lk.colours)]
                           if v < len(lk.colours) else (90, 90, 90),
                           radius=s * 0.12, group=self.body_group)
            if v >= len(lk.colours):
                self._text(str(v), x + s / 2, y + s / 2, s * 0.4, bold=True,
                           colour=(255, 255, 255, 255))
        elif kind == 1:
            glyphpaint.glyph(self, lk, G.Glyph(v, 0, 1, 1, 0, 1, -1), x, y,
                             s, s, colour=(70, 70, 80))
        elif kind == 2:
            for k in range(v + 1):
                cx = x + s * (0.2 + 0.6 * (k % 3) / 2)
                cy = y + s * (0.78 - 0.28 * (k // 3))
                self.drawn.append(pyglet.shapes.Circle(
                    cx, cy, s * 0.09, color=(240, 180, 40),
                    batch=self.batch, group=self.top_group))
        elif kind == 3:
            self._text(LETTERS[v], x + s / 2, y + s / 2, s * 0.55, bold=True,
                       colour=(40, 40, 60, 255))
        else:
            polish.rounded(self.drawn, self.batch, x + s * 0.15, y + s * 0.3,
                           s * 0.7, s * 0.45, self.flags[v], radius=3,
                           group=self.body_group)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        n = p.level.houses
        house_h = height * 0.3
        hw = min(width / n * 0.85, house_h * 1.1)
        gap = (width - hw * n) / (n + 1)
        for h in range(n):
            x = left + gap + h * (hw + gap)
            border, thick = self._mark(h)
            polish.card(self.drawn, self.batch, x, bottom, hw, house_h * 0.7,
                        (244, 236, 222), radius=6,
                        edge=border if thick > 2 else (180, 160, 140),
                        group=self.card_group)
            self.drawn.append(pyglet.shapes.Triangle(
                x - hw * 0.06, bottom + house_h * 0.7, x + hw * 1.06,
                bottom + house_h * 0.7, x + hw / 2, bottom + house_h,
                color=border if thick > 2 else (170, 80, 60),
                batch=self.batch, group=self.card_group))
            self._text(str(h + 1), x + hw / 2, bottom + house_h * 0.35,
                       calc_fontsize(20), bold=True)
            self.hits.append((x, bottom, hw, house_h,
                              lambda c=h: self.choose(c)))
        # The asked thing, by the question.
        top = bottom + house_h + height * 0.04
        s = height * 0.12
        self._text(_('Where is'), left + width * 0.42, top + s / 2,
                   calc_fontsize(15), anchor='right', bold=True)
        polish.card(self.drawn, self.batch, left + width * 0.44, top, s, s,
                    (255, 255, 255), radius=8, group=self.card_group)
        self._thing(p.asked, left + width * 0.44, top, s)
        self._text('?', left + width * 0.44 + s * 1.2, top + s / 2,
                   calc_fontsize(18), bold=True)
        # The clues.
        area_y = top + s + height * 0.03
        area_h = bottom + height - area_y
        k = len(p.clues)
        cols = 3 if k > 6 else 2
        rows = (k + cols - 1) // cols
        ch = min(area_h / rows, height * 0.14)
        cw = width / cols
        for i, (kind, a, b) in enumerate(p.clues):
            col, rw = i % cols, i // cols
            x = left + col * cw + cw * 0.08
            y = bottom + height - (rw + 1) * ch
            polish.card(self.drawn, self.batch, x, y + ch * 0.06, cw * 0.84,
                        ch * 0.88, (250, 250, 246), radius=8,
                        group=self.card_group)
            b_ = ch * 0.76
            self._thing(a, x + cw * 0.08, y + ch * 0.12, b_)
            if kind == model.AT:
                self._text('@ %d' % (b + 1), x + cw * 0.5, y + ch / 2,
                           ch * 0.36, bold=True)
            else:
                self._text(SIGNS[kind], x + cw * 0.42, y + ch / 2,
                           ch * 0.45, bold=True)
                self._thing(b, x + cw * 0.84 - b_ - cw * 0.08,
                            y + ch * 0.12, b_)
