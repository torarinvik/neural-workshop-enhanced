# -*- coding: utf-8 -*-
"""Looking back, on screen: frames go by, then a question about one of
them that is no longer showing.

The answer cards are up throughout and a question mark joins them when
the question is put; presses before that are ignored.

For the agent boundary: Shape Back has three ports, one a card; Hidden
Cue four, one a square; Sound Back three, low, middle and high.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import lookback as model
from ..i18n import _
from .showtask import ShowTask
from .twins import shape


class BackTask(ShowTask):
    """A run of frames and a question about an earlier one."""

    KIND = ''
    CATEGORY = 'first_steps'
    BUTTONS = 0
    FEEDBACK = 1.2
    FOOTNOTE = _('wait for the question mark, then click an answer or '
                 'press its number   Esc: menu')

    def _make(self):
        return model.deal(self.KIND, self.rung, rng=self.rng)

    def _hue(self):
        hue = model.HUES[self.puzzle.data['hue']]
        return tuple(min(255, c + 70) for c in hue) if self.dark else hue

    def _asked(self, x, y, size) -> None:
        if self.run is not None and self.run.open:
            self._text('?', x, y, size, bold=True)

    def _draw_at(self, left, bottom, width, height, t) -> None:
        getattr(self, '_draw_' + self.KIND)(left, bottom, width, height, t)

    def _draw_shape(self, left, bottom, width, height, t) -> None:
        p, hue = self.puzzle, self._hue()
        card = min(width * 0.16, height * 0.26)
        stage_b = bottom + card * 1.25
        stage_h = height - card * 1.25
        self._box(left + width * 0.1, stage_b, width * 0.8, stage_h, None,
                  self.ink, thickness=1.5)
        f, showing = model.frame_at(p, t)
        if showing:
            fx, fy = p.data['spots'][f]
            shape(self, p.data['kinds'][p.frames[f]],
                  left + width * (0.1 + 0.8 * fx), stage_b + stage_h * fy,
                  min(width, stage_h) * 0.13, hue)
        x0 = left + (width - card * 3.4) / 2
        for port in range(3):
            x = x0 + port * card * 1.2
            self._card(port, x, bottom, card, card)
            shape(self, p.data['kinds'][p.data['cards'][port]],
                  x + card / 2, bottom + card * 0.45, card * 0.26, hue,
                  group=self.text_group)
        self._asked(x0 - card * 0.5, bottom + card / 2, card * 0.5)

    def _draw_cue(self, left, bottom, width, height, t) -> None:
        p, hue = self.puzzle, self._hue()
        layout = p.data['layout']
        cols, rows = {'row': (4, 1), 'column': (1, 4),
                      'square': (2, 2)}[layout]
        cell = min(width * 0.8 / cols, height * 0.9 / rows)
        x0 = left + (width - cell * cols) / 2
        y0 = bottom + (height - cell * rows) / 2
        f, showing = model.frame_at(p, t)
        for port in range(4):
            x = x0 + (port % cols) * cell
            y = y0 + (rows - 1 - port // cols) * cell
            self._card(port, x + cell * 0.06, y + cell * 0.06, cell * 0.88,
                       cell * 0.88, number=False)
            if f == 0 and showing and p.frames[0] == port:
                self.drawn.append(pyglet.shapes.Rectangle(
                    x + cell * 0.2, y + cell * 0.2, cell * 0.6, cell * 0.6,
                    color=hue, batch=self.batch, group=self.text_group))
        self._asked(left + width * 0.06, bottom + height / 2, cell * 0.4)

    def _draw_sound(self, left, bottom, width, height, t) -> None:
        p, hue = self.puzzle, self._hue()
        f, showing = model.frame_at(p, t)
        r = min(width, height) * 0.12
        cx, cy = left + width / 2, bottom + height * 0.72
        self.drawn.append(pyglet.shapes.Circle(
            cx, cy, r * (1.25 if showing and t - f * model.FRAME
                         < model.SHOWN else 1.0),
            color=hue, batch=self.batch, group=self.body_group))
        card = min(width * 0.16, height * 0.36)
        x0 = left + (width - card * 3.4) / 2
        for port in range(3):
            x = x0 + port * card * 1.2
            self._card(port, x, bottom, card, card)
            self.drawn.append(pyglet.shapes.Rectangle(
                x + card * 0.36, bottom + card * 0.12, card * 0.28,
                card * (0.2 + 0.27 * port), color=hue, batch=self.batch,
                group=self.text_group))
        self._asked(x0 - card * 0.5, bottom + card / 2, card * 0.5)


class ShapeBack(BackTask):
    """Which shape was showing k frames ago?"""
    instance: Optional['ShapeBack'] = None
    TITLE, TASK_ID, PREFIX = 'Shape Back', 'shape_back', 'SHAPEBACK'
    KIND = 'shape'


class HiddenCue(BackTask):
    """A square lights, then hides for k frames: which was it?"""
    instance: Optional['HiddenCue'] = None
    TITLE, TASK_ID, PREFIX = 'Hidden Cue', 'hidden_cue', 'HIDDENCUE'
    KIND = 'cue'


class SoundBack(BackTask):
    """Which tone sounded k frames ago: low, middle or high?"""
    instance: Optional['SoundBack'] = None
    TITLE, TASK_ID, PREFIX = 'Sound Back', 'sound_back', 'SOUNDBACK'
    KIND = 'sound'
