# -*- coding: utf-8 -*-
"""The twin tasks on screen: four rules, each in two looks.

Look a is drawn in shapes, in blues and purples, laid out across the
page; look b in tiles, stripes and pips, in browns and ochres, laid out
down it or round a ring, with its ports in the other order.

For the agent boundary: one port a choice. Same or different and inside
or outside have two; the odd one out has one an item; what comes next
has three, one a card.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet

from .. import twins as model
from ..geometry import calc_fontsize
from ..i18n import _
from .spacetask import ChoiceTask


def shape(task, name: str, cx: float, cy: float, r: float, colour,
          group=None, hollow: bool = False) -> None:
    """One of the six plain shapes, centred, about *r* in radius."""
    group = group or task.body_group
    kw = dict(color=colour, batch=task.batch, group=group)
    add = task.drawn.append
    if name == 'circle':
        add(pyglet.shapes.Circle(cx, cy, r, **kw))
    elif name == 'square':
        k = r * 0.86
        add(pyglet.shapes.Rectangle(cx - k, cy - k, 2 * k, 2 * k, **kw))
    elif name == 'triangle':
        add(pyglet.shapes.Triangle(cx - r, cy - r * 0.8, cx + r,
                                   cy - r * 0.8, cx, cy + r, **kw))
    elif name == 'diamond':
        add(pyglet.shapes.Polygon((cx, cy + r), (cx + r * 0.72, cy),
                                  (cx, cy - r), (cx - r * 0.72, cy), **kw))
    elif name == 'star':
        add(pyglet.shapes.Star(cx, cy, r, r * 0.45, 5, rotation=-18, **kw))
    else:                                     # a cross
        k = r * 0.34
        add(pyglet.shapes.Rectangle(cx - r, cy - k, 2 * r, 2 * k, **kw))
        add(pyglet.shapes.Rectangle(cx - k, cy - r, 2 * k, 2 * r, **kw))
    if hollow:
        shape(task, 'circle' if name in ('circle', 'star') else 'square',
              cx, cy, r * 0.34, task.paper, group=task.top_group)


class TwinTask(ChoiceTask):
    """One rule in one look."""

    RULE = ''
    LOOK = 'a'
    CATEGORY = 'first_steps'
    FEEDBACK = 1.2

    def _make(self):
        return model.deal(self.RULE, self.LOOK, self.rung, rng=self.rng)

    def _hue(self):
        hues = model.HUES_A if self.LOOK == 'a' else model.HUES_B
        hue = hues[self.puzzle.data['hue'] % len(hues)]
        if self.dark:
            hue = tuple(min(255, c + 70) for c in hue)
        return hue

    def _draw_scene(self, left, bottom, width, height) -> None:
        getattr(self, '_%s_%s' % (self.RULE, self.LOOK))(left, bottom,
                                                        width, height)

    def _rows(self, n: int, per: int):
        return [(k % per, k // per) for k in range(n)], \
            min(n, per), (n + per - 1) // per

    # --- same or different -----------------------------------------------

    def _same_a(self, left, bottom, width, height) -> None:
        data, hue = self.puzzle.data, self._hue()
        for side, items in enumerate((data['one'], data['two'])):
            x = left + width * (0.02 + 0.5 * side)
            w = width * 0.46
            self._box(x, bottom + height * 0.1, w, height * 0.8, None,
                      self.ink, thickness=1.5)
            at, cols, rows = self._rows(len(items), 4)
            cell = min(w / cols, height * 0.8 / rows) * 0.9
            for name, (cx, cy) in zip(items, at):
                shape(self, name,
                      x + w / 2 + (cx - (cols - 1) / 2) * cell,
                      bottom + height / 2 - (cy - (rows - 1) / 2) * cell,
                      cell * 0.34, hue)

    def _same_b(self, left, bottom, width, height) -> None:
        data = self.puzzle.data
        n = len(data['one'])
        cell = min(width * 0.9 / n, height * 0.3)
        for row, items in enumerate((data['one'], data['two'])):
            y = bottom + height * (0.6 if row == 0 else 0.12)
            x0 = left + (width - cell * n) / 2
            for k, hue in enumerate(items):
                self.drawn.append(pyglet.shapes.Rectangle(
                    x0 + k * cell + cell * 0.06, y, cell * 0.88,
                    cell * 0.88, color=model.HUES_B[hue], batch=self.batch,
                    group=self.body_group))

    # --- the odd one out -------------------------------------------------

    def _odd_a(self, left, bottom, width, height) -> None:
        items, hue = self.puzzle.data['items'], self._hue()
        n = len(items)
        cell = min(width / n, height * 0.6)
        x0 = left + (width - cell * n) / 2
        y = bottom + (height - cell) / 2
        for k, name in enumerate(items):
            self._card(k, x0 + k * cell + cell * 0.05, y, cell * 0.9,
                       cell * 0.9, number=cell > 60)
            shape(self, name, x0 + (k + 0.5) * cell, y + cell * 0.45,
                  cell * 0.26, hue, group=self.text_group)

    def _odd_b(self, left, bottom, width, height) -> None:
        data, hue = self.puzzle.data, self._hue()
        items = data['items']
        n = len(items)
        ring = min(width, height) * 0.36
        r = min(ring * math.sin(math.pi / n) * 0.8, ring * 0.42)
        cx, cy = left + width / 2, bottom + height / 2
        for k, tilt in enumerate(items):
            a = math.tau * (data['turn'] + k / n)
            x, y = cx + ring * math.sin(a), cy + ring * math.cos(a)
            self._card(n - 1 - k, x - r, y - r, 2 * r, 2 * r,
                       number=False)
            self.drawn.append(pyglet.shapes.Circle(
                x, y, r * 0.8, color=hue, batch=self.batch,
                group=self.text_group))
            t = math.radians(45 * tilt)
            ux, uy = math.cos(t), math.sin(t)
            for off in (-0.36, 0.0, 0.36):
                half = r * 0.8 * math.sqrt(1 - off * off)
                ox, oy = -uy * off * r * 0.8, ux * off * r * 0.8
                self.drawn.append(pyglet.shapes.Line(
                    x + ox - ux * half, y + oy - uy * half,
                    x + ox + ux * half, y + oy + uy * half,
                    thickness=max(2.0, r * 0.12), color=self.paper,
                    batch=self.batch, group=self.top_group))

    # --- what comes next -------------------------------------------------

    def _pips(self, x, y, size, count, hue, group=None) -> None:
        self.drawn.append(pyglet.shapes.Box(
            x, y, size, size, thickness=max(1.5, size * 0.06), color=hue,
            batch=self.batch, group=group or self.body_group))
        for k in range(count):
            self.drawn.append(pyglet.shapes.Circle(
                x + size * (k + 1) / (count + 1), y + size / 2,
                size * 0.11, color=hue, batch=self.batch,
                group=group or self.body_group))

    def _next_a(self, left, bottom, width, height) -> None:
        data, hue = self.puzzle.data, self._hue()
        seq = data['seq']
        per = 14
        rows = (len(seq) + per) // per
        cell = min(width / per, height * 0.5 / rows)
        top = bottom + height - cell * 0.6
        for k in range(len(seq) + 1):
            x = left + (width - cell * min(per, len(seq) + 1)) / 2 \
                + (k % per + 0.5) * cell
            y = top - (k // per) * cell
            if k == len(seq):
                self._text('?', x, y, cell * 0.5, bold=True)
            else:
                shape(self, data['kinds'][seq[k]], x, y, cell * 0.32, hue)
        card = min(width * 0.2, height * 0.3)
        x0 = left + (width - card * 3.4) / 2
        for port in range(3):
            x = x0 + port * card * 1.2
            self._card(port, x, bottom, card, card)
            shape(self, data['kinds'][data['cards'][port]], x + card / 2,
                  bottom + card * 0.45, card * 0.26, hue,
                  group=self.text_group)

    def _next_b(self, left, bottom, width, height) -> None:
        data, hue = self.puzzle.data, self._hue()
        seq = data['seq']
        per = 8                                # tiles down each column
        cols = (len(seq) + per) // per
        cell = min(height / per, width * 0.6 / cols)
        x0 = left + width * 0.04
        for k in range(len(seq) + 1):
            x = x0 + (k // per) * cell * 1.15
            y = bottom + height - (k % per + 1) * cell
            if k == len(seq):
                self._text('?', x + cell * 0.45, y + cell * 0.45,
                           cell * 0.5, bold=True)
            else:
                self._pips(x, y + cell * 0.05, cell * 0.9,
                           data['kinds'][seq[k]], hue)
        card = min(height * 0.3, width * 0.2)
        x = left + width - card * 1.3
        for port in range(3):
            y = bottom + port * (height - card) / 2
            self._card(port, x, y, card, card, number=False)
            self._pips(x + card * 0.2, y + card * 0.2, card * 0.6,
                       data['kinds'][data['cards'][port]], hue,
                       group=self.text_group)

    # --- inside or outside -----------------------------------------------

    def _inside_a(self, left, bottom, width, height) -> None:
        data, hue = self.puzzle.data, self._hue()
        k = min(width, height) * 0.46
        cx, cy = left + width / 2, bottom + height / 2
        pts = [(cx + x * k, cy + y * k) for x, y in data['points']]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            self.drawn.append(pyglet.shapes.Line(
                x1, y1, x2, y2, thickness=3.0, color=hue,
                batch=self.batch, group=self.body_group))
        x, y = data['dot']
        self.drawn.append(pyglet.shapes.Circle(
            cx + x * k, cy + y * k, max(5.0, k * 0.035), color=self.ink,
            batch=self.batch, group=self.text_group))

    def _inside_b(self, left, bottom, width, height) -> None:
        data, hue = self.puzzle.data, self._hue()
        x0, y0, x1, y1 = data['box']
        cols, rows = x1 - x0 + 1, y1 - y0 + 1
        cell = min(width / cols, height / rows)
        ox = left + (width - cell * cols) / 2
        oy = bottom + (height - cell * rows) / 2
        cells = data['cells']
        for (x, y) in cells:
            px, py = ox + (x - x0) * cell, oy + (y - y0) * cell
            for dx, dy, ends in (
                    (1, 0, (px + cell, py, px + cell, py + cell)),
                    (-1, 0, (px, py, px, py + cell)),
                    (0, 1, (px, py + cell, px + cell, py + cell)),
                    (0, -1, (px, py, px + cell, py))):
                if (x + dx, y + dy) not in cells:
                    self.drawn.append(pyglet.shapes.Line(
                        *ends, thickness=max(3.0, cell * 0.07), color=hue,
                        batch=self.batch, group=self.body_group))
        mx, my = data['mark']
        shape(self, 'cross', ox + (mx - x0 + 0.5) * cell,
              oy + (my - y0 + 0.5) * cell, cell * 0.2, self.ink,
              group=self.text_group)


class MatchShapes(TwinTask):
    """Two sets of shapes: the same, or different?"""
    instance: Optional['MatchShapes'] = None
    TITLE, TASK_ID, PREFIX = 'Match Shapes', 'match_shapes', 'MATCHSHAPES'
    RULE, LOOK = 'same', 'a'


class MatchTiles(TwinTask):
    """Two strips of tiles: the same, or different?"""
    instance: Optional['MatchTiles'] = None
    TITLE, TASK_ID, PREFIX = 'Match Tiles', 'match_tiles', 'MATCHTILES'
    RULE, LOOK = 'same', 'b'


class OddShape(TwinTask):
    """A row of shapes, one of them another shape."""
    instance: Optional['OddShape'] = None
    TITLE, TASK_ID, PREFIX = 'Odd Shape', 'odd_shape', 'ODDSHAPE'
    RULE, LOOK, BUTTONS = 'odd', 'a', 0
    FOOTNOTE = _('click the odd one out   Esc: menu')


class OddStripe(TwinTask):
    """A ring of striped discs, one striped another way."""
    instance: Optional['OddStripe'] = None
    TITLE, TASK_ID, PREFIX = 'Odd Stripe', 'odd_stripe', 'ODDSTRIPE'
    RULE, LOOK, BUTTONS = 'odd', 'b', 0
    FOOTNOTE = _('click the odd one out   Esc: menu')


class NextShape(TwinTask):
    """A run of shapes that repeats: which comes next?"""
    instance: Optional['NextShape'] = None
    TITLE, TASK_ID, PREFIX = 'Next Shape', 'next_shape', 'NEXTSHAPE'
    RULE, LOOK, BUTTONS = 'next', 'a', 0
    FOOTNOTE = _('click what comes next, or press 1-3   Esc: menu')


class NextTile(TwinTask):
    """A run of pip tiles that repeats: which comes next?"""
    instance: Optional['NextTile'] = None
    TITLE, TASK_ID, PREFIX = 'Next Tile', 'next_tile', 'NEXTTILE'
    RULE, LOOK, BUTTONS = 'next', 'b', 0
    FOOTNOTE = _('click what comes next, or press 1-3   Esc: menu')


class InTheLoop(TwinTask):
    """An outline and a dot: inside, or outside?"""
    instance: Optional['InTheLoop'] = None
    TITLE, TASK_ID, PREFIX = 'In the Loop', 'in_the_loop', 'INTHELOOP'
    RULE, LOOK = 'inside', 'a'


class InThePen(TwinTask):
    """A fence on squared paper and a mark: outside, or inside?"""
    instance: Optional['InThePen'] = None
    TITLE, TASK_ID, PREFIX = 'In the Pen', 'in_the_pen', 'INTHEPEN'
    RULE, LOOK = 'inside', 'b'
