# -*- coding: utf-8 -*-
"""Signals on screen: the partner, the objects, and eight glyphs.

The partner's panel at the top shows what it says when it speaks, or the
glyphs being put together when the player does. The objects sit in a
row in the middle -- the one to signal outlined when it is the player's
turn. The eight glyph keys run along the bottom. On the right, the last
few exchanges: what was said, what was meant, what was picked.

Keys: 1-8 pick objects; Q W E R T Y U I send glyphs one to eight.

For the agent boundary: ports 0-7 pick objects, ports 8-15 send glyphs.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import signals as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

GLYPH = model.MOST_OBJECTS
PORTS = GLYPH + model.GLYPHS

COLOURS = ((220, 60, 50), (50, 100, 220), (50, 170, 80), (235, 200, 40))
PANEL_LIGHT = (232, 235, 240)
PANEL_DARK = (46, 50, 58)
TARGET = (40, 40, 40)
GLYPH_KEYS = (key.Q, key.W, key.E, key.R, key.T, key.Y, key.U, key.I)

#: Each glyph as strokes in a unit square, y up.
STROKES = (
    (((0.5, 0.1), (0.5, 0.9)), ((0.2, 0.9), (0.8, 0.9))),
    (((0.15, 0.15), (0.85, 0.85)), ((0.15, 0.85), (0.85, 0.15))),
    (((0.1, 0.2), (0.35, 0.8)), ((0.35, 0.8), (0.65, 0.2)),
     ((0.65, 0.2), (0.9, 0.8))),
    (((0.2, 0.9), (0.2, 0.2)), ((0.2, 0.2), (0.8, 0.2)),
     ((0.8, 0.2), (0.8, 0.5))),
    (((0.15, 0.85), (0.85, 0.85)), ((0.85, 0.85), (0.15, 0.15)),
     ((0.15, 0.15), (0.85, 0.15))),
    (((0.1, 0.1), (0.5, 0.9)), ((0.5, 0.9), (0.9, 0.1)),
     ((0.3, 0.5), (0.7, 0.5))),
    (((0.2, 0.35), (0.8, 0.35)), ((0.2, 0.65), (0.8, 0.65)),
     ((0.5, 0.1), (0.5, 0.9))),
    (((0.2, 0.2), (0.8, 0.2)), ((0.8, 0.2), (0.8, 0.8)),
     ((0.8, 0.8), (0.35, 0.8)), ((0.35, 0.8), (0.35, 0.45)),
     ((0.35, 0.45), (0.6, 0.45))),
)


class Signals(RungTask):
    """Learn a partner's code, and use it both ways."""

    instance: Optional['Signals'] = None

    TITLE = 'Signals'
    TASK_ID = 'signals'
    PREFIX = 'SIGNALS'
    CATEGORY = 'reasoning'
    FEEDBACK = 2.8
    FOOTNOTE = _('listening: click the object meant (1-8)   speaking: click '
                 'glyphs (Q-I)   Esc: menu')

    def __init__(self) -> None:
        self.game: Optional[model.Game] = None
        self.par = 0.0
        super().__init__()

    def _clear_trial(self) -> None:
        self.game = None

    def _deal(self) -> bool:
        dealt = model.deal(self.rung, rng=self.rng)
        self.game = model.Game(dealt)
        self.par = model.par(dealt)
        self._say_whose_turn()
        return True

    def _say_whose_turn(self) -> None:
        ex = self.game.exchange
        if ex is None:
            return
        if ex.role == 'partner':
            self.message = _('Your partner means one of these. Which?')
        elif self.game.deal.level.length == 2:
            self.message = _('Send two glyphs so your partner picks the '
                             'outlined one')
        else:
            self.message = _('Send a glyph so your partner picks the '
                             'outlined one')

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if port < GLYPH:
            self.pick(port)
        else:
            self.say(port - GLYPH)

    def pick(self, index: int) -> None:
        if self.phase == self.PLAY and self.game.pick(index) is not None:
            self._after()

    def say(self, glyph: int) -> None:
        if self.phase != self.PLAY:
            return
        before = self.game.at
        self.game.say(glyph)
        if self.game.at != before:
            self._after()
        else:
            self._redraw()

    def _after(self) -> None:
        game = self.game
        if not game.over:
            self._say_whose_turn()
            self._redraw()
            return
        self._judge(game.score >= self.par - 1e-9,
                    _('%d of %d exchanges understood (par %s)')
                    % (game.score, len(game.deal.exchanges),
                       _points(self.par)))

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._8:
            self.pick(symbol - key._1)
        elif symbol in GLYPH_KEYS:
            self.say(GLYPH_KEYS.index(symbol))

    # --- drawing ---------------------------------------------------------

    def _glyph(self, g, x, y, size, colour=None, width=None) -> None:
        colour = colour or self.ink
        for (ax, ay), (bx, by) in STROKES[g]:
            self.drawn.append(pyglet.shapes.Line(
                x + ax * size, y + ay * size, x + bx * size, y + by * size,
                thickness=width or max(2.0, size * 0.08), color=colour,
                batch=self.batch, group=self.text_group))

    def _thing(self, thing, cx, cy, r) -> None:
        colour, shape = COLOURS[thing[0]], thing[1]
        group = self.body_group
        if shape == 0:
            self.drawn.append(pyglet.shapes.Circle(
                cx, cy, r, color=colour, batch=self.batch, group=group))
        elif shape == 1:
            self.drawn.append(pyglet.shapes.Rectangle(
                cx - r * 0.85, cy - r * 0.85, r * 1.7, r * 1.7,
                color=colour, batch=self.batch, group=group))
        elif shape == 2:
            self.drawn.append(pyglet.shapes.Triangle(
                cx - r, cy - r * 0.8, cx + r, cy - r * 0.8, cx, cy + r,
                color=colour, batch=self.batch, group=group))
        else:
            self.drawn.append(pyglet.shapes.Star(
                cx, cy, r, r * 0.45, 5, rotation=0, color=colour,
                batch=self.batch, group=group))

    def _draw(self, left, bottom, width, height) -> None:
        game = self.game
        back = PANEL_DARK if self.dark else PANEL_LIGHT
        side = width * 0.24
        main = width - side - width * 0.02
        self._draw_partner(left, bottom + height * 0.72, main, height * 0.28,
                           back)
        self._draw_objects(left, bottom + height * 0.3, main, height * 0.38)
        self._draw_keys(left, bottom, main, height * 0.24, back)
        self._draw_history(left + main + width * 0.02, bottom, side, height,
                           back)

    def _draw_partner(self, left, bottom, width, height, back) -> None:
        game = self.game
        self._box(left, bottom, width, height, back, self.ink)
        size = calc_fontsize(13)
        ex = game.exchange
        if ex is None:
            return
        speaking = ex.role == 'partner'
        self._text(_('Partner says') if speaking else _('You say'),
                   left + 16, bottom + height - size * 1.4, size,
                   anchor='left', bold=True)
        glyphs = game.heard() if speaking else tuple(game.drafted)
        slots = game.deal.level.length
        g = min(height * 0.55, width * 0.12)
        x0 = left + width / 2 - (slots * g * 1.4) / 2
        for slot in range(slots):
            x = x0 + slot * g * 1.4
            y = bottom + height * 0.12
            self._box(x - 6, y - 6, g + 12, g + 12, None, self.ink)
            if slot < len(glyphs):
                self._glyph(glyphs[slot], x, y, g)

    def _draw_objects(self, left, bottom, width, height) -> None:
        game = self.game
        ex = game.exchange
        if ex is None:
            return
        n = len(ex.objects)
        cell = min(width / n, height)
        x0 = left + (width - cell * n) / 2
        size = calc_fontsize(11)
        for i, thing in enumerate(ex.objects):
            cx = x0 + cell * (i + 0.5)
            cy = bottom + height * 0.55
            r = cell * 0.3
            if ex.role == 'player' and i == ex.target:
                self._box(cx - r * 1.4, cy - r * 1.4, r * 2.8, r * 2.8,
                          None, self.ink, thickness=4)
            self._thing(thing, cx, cy, r)
            self._text('%d' % (i + 1), cx, bottom + height * 0.08, size,
                       bold=True)
            if ex.role == 'partner':
                self.hits.append((cx - cell / 2, bottom, cell, height,
                                  lambda c=i: self.pick(c)))

    def _draw_keys(self, left, bottom, width, height, back) -> None:
        game = self.game
        ex = game.exchange
        active = ex is not None and ex.role == 'player'
        n = model.GLYPHS
        gap = width * 0.012
        w = (width - gap * (n - 1)) / n
        g = min(w, height) * 0.6
        letters = 'QWERTYUI'
        for i in range(n):
            x = left + i * (w + gap)
            self._box(x, bottom, w, height, back,
                      self.ink if active else (150, 150, 150))
            self._glyph(i, x + (w - g) / 2, bottom + (height - g) / 2 + 6, g,
                        colour=None if active else (150, 150, 150))
            self._text(letters[i], x + 8, bottom + 10,
                       calc_fontsize(9), anchor='left')
            if active:
                self.hits.append((x, bottom, w, height,
                                  lambda c=i: self.say(c)))

    def _draw_history(self, left, bottom, width, height, back) -> None:
        game = self.game
        self._box(left, bottom, width, height, back, self.ink)
        size = calc_fontsize(11)
        self._text(_('Last: meant > taken'), left + width / 2,
                   bottom + height - size * 1.4, size, bold=True)
        rows = 6
        row = (height - size * 3) / rows
        for k, (ex, signal, picked, right) in enumerate(
                reversed(game.history[-rows:])):
            y = bottom + height - size * 3 - (k + 1) * row
            g = min(row * 0.55, width * 0.14)
            x = left + 10
            self._text(_('them') if ex.role == 'partner' else _('you'),
                       x, y + row / 2, size * 0.8, anchor='left')
            x += width * 0.2
            for glyph in signal:
                self._glyph(glyph, x, y + (row - g) / 2, g, width=2)
                x += g * 1.15
            # What was meant, and -- when it went wrong -- what was
            # taken instead: the evidence a code is learned from.
            x = left + width * 0.6
            self._thing(ex.objects[ex.target], x, y + row / 2, g * 0.4)
            if not right:
                self._text('>', x + g * 0.65, y + row / 2, size * 0.8)
                self._thing(ex.objects[picked], x + g * 1.3, y + row / 2,
                            g * 0.4)
            self._text(_('right') if right else _('wrong'),
                       left + width - 10, y + row / 2, size * 0.8,
                       anchor='right', bold=right)

    def _facts(self) -> str:
        game = self.game
        if game is None:
            return ''
        return (_('rung %d  %d/%d   exchange %d of %d   understood %d   '
                  'par %s')
                % (self.rung, self.trial, self.total_trials,
                   min(game.at + 1, len(game.deal.exchanges)),
                   len(game.deal.exchanges), game.score, _points(self.par)))


def _points(value: float) -> str:
    return ('%d' % value) if float(value).is_integer() else ('%.1f' % value)
