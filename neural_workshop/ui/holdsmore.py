# -*- coding: utf-8 -*-
"""Holds More on screen: containers side on, with a hint of their
round rims; water, and marks, when it is poured.

For the agent boundary: port k picks container k, or mark k (low,
middle, high) when poured.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import holdsmore as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import polish
from .spacetask import ChoiceTask

WATER = (90, 150, 230)


class HoldsMore(ChoiceTask):
    """Which holds the most? Where will the water come to?"""

    instance: Optional['HoldsMore'] = None

    TITLE = 'Holds More'
    TASK_ID = 'holds_more'
    PREFIX = 'HOLDS'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')

    def _make(self):
        p = model.deal(self.rung, rng=self.rng)
        self.BUTTONS = 0.13 if p.poured is not None else 0
        return p

    def _jar(self, prof, cx, base, scale, hue, water=None, marks=()) -> None:
        pts_l = [(cx - r * scale, base + h * scale) for h, r in prof]
        pts_r = [(cx + r * scale, base + h * scale) for h, r in prof]
        body = pts_l + pts_r[::-1]
        self.drawn.append(pyglet.shapes.Polygon(
            *body, color=polish.lighter(hue, 0.3), batch=self.batch,
            group=self.card_group))
        if water is not None:
            sub = [(h, r) for h, r in prof if h <= water]
            top_r = None
            for (h0, r0), (h1, r1) in zip(prof, prof[1:]):
                if h0 <= water <= h1:
                    top_r = r0 + (r1 - r0) * (water - h0) / max(1e-9, h1 - h0)
            sub.append((water, top_r if top_r is not None else prof[-1][1]))
            wl = [(cx - r * scale, base + h * scale) for h, r in sub]
            wr = [(cx + r * scale, base + h * scale) for h, r in sub]
            self.drawn.append(pyglet.shapes.Polygon(
                *(wl + wr[::-1]), color=WATER, batch=self.batch,
                group=self.body_group))
        edge = polish.darker(hue, 0.45)
        for a, b in zip(pts_l, pts_l[1:]):
            self._line(a, b, edge)
        for a, b in zip(pts_r, pts_r[1:]):
            self._line(a, b, edge)
        self._line(pts_l[0], pts_r[0], edge)
        top_r = prof[-1][1] * scale
        self.drawn.append(pyglet.shapes.Ellipse(
            cx, base + prof[-1][0] * scale, top_r, max(2, top_r * 0.18),
            color=polish.darker(hue, 0.15), batch=self.batch,
            group=self.top_group))
        for k, m in enumerate(marks):
            y = base + m * scale
            r = max(r for _h, r in prof) * scale
            self._line((cx + r + 4, y), (cx + r + 26, y), (40, 40, 40))
            self._text(str(k + 1), cx + r + 34, y, calc_fontsize(12),
                       anchor='left', bold=True)

    def _line(self, a, b, colour) -> None:
        self.drawn.append(pyglet.shapes.Line(a[0], a[1], b[0], b[1],
                                             thickness=3, color=colour,
                                             batch=self.batch,
                                             group=self.top_group))

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        n = len(p.jars)
        tallest = max(j[-1][0] for j in p.jars)
        widest = max(max(r for _h, r in j) for j in p.jars)
        scale = min(height * 0.82 / tallest, width / n * 0.4 / widest)
        base = bottom + height * 0.06
        for k, prof in enumerate(p.jars):
            cx = left + width * (k + 0.5) / n
            water = marks = None
            if p.poured is not None:
                water = p.poured[2] if k == p.poured[0] else None
                marks = p.marks if k == p.poured[1] else ()
            hue = p.hues[k % len(p.hues)]
            if p.poured is None:
                border, thick = self._mark(k)
                if thick > 2:
                    hue = border
                w = widest * scale * 2.4
                self.hits.append((cx - w / 2, bottom, w, height,
                                  lambda c=k: self.choose(c)))
                self._text(str(k + 1), cx, bottom + height - 6,
                           calc_fontsize(13), anchor_y='top', bold=True)
            self._jar(prof, cx, base, scale, hue, water, marks or ())
