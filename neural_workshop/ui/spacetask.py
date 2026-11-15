# -*- coding: utf-8 -*-
"""The screen the spatial tasks share: a scene above, answers below.

Same or Mirror?, Which Is Nearer?, Shape from Motion, Fold It and Point
of View each deal a puzzle with ``choices`` and an ``answer``, draw a
scene, and take one choice -- a click on a button (or on a figure the
task makes clickable), a number key, or an agent port. A subclass gives
:meth:`_make` and :meth:`_draw_scene`; everything else is here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from ..geometry import calc_fontsize
from ..i18n import _
from . import spacepaint
from .rungtask import RungTask

BUTTON_LIGHT = (232, 235, 240)
BUTTON_DARK = (46, 50, 58)
RIGHT = (60, 170, 90)
WRONG = (214, 64, 58)


class ChoiceTask(RungTask):
    """One spatial question a trial, one answer."""

    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    #: Share of the playing area the answer buttons take; 0 for none
    #: (the scene's own figures are the buttons).
    BUTTONS = 0.13

    def __init__(self) -> None:
        self.puzzle = None
        self.chosen: Optional[int] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.chosen = None

    def _deal(self) -> bool:
        self.puzzle = self._make()
        self.chosen = None
        self.message = self.puzzle.question
        return True

    def _make(self):
        raise NotImplementedError

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        self.choose(port)

    def choose(self, index: int) -> None:
        if self.phase != self.PLAY or self.puzzle is None \
                or not 0 <= index < len(self.puzzle.choices):
            return
        self.chosen = index
        right = index == self.puzzle.answer
        self._judge(right, self._verdict(right))

    def _verdict(self, right: bool) -> str:
        truth = self.puzzle.choices[self.puzzle.answer]
        return (_('Right: %s') if right else _('No: %s')) % truth

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._9:
            self.choose(symbol - key._1)

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        spacepaint.begin(self)
        buttons = height * self.BUTTONS
        if buttons:
            self._draw_buttons(left, bottom, width, buttons)
            gap = height * 0.03
            self._draw_scene(left, bottom + buttons + gap, width,
                             height - buttons - gap)
        else:
            self._draw_scene(left, bottom, width, height)

    def _draw_scene(self, left, bottom, width, height) -> None:
        raise NotImplementedError

    def _mark(self, index: int):
        """Border colour and thickness for choice *index*."""
        if self.phase == 'judged':
            if index == self.puzzle.answer:
                return RIGHT, 5
            if index == self.chosen:
                return WRONG, 5
        return self.ink, 2

    def _draw_buttons(self, left, bottom, width, height) -> None:
        choices = self.puzzle.choices
        n = len(choices)
        gap = width * 0.012
        bw = min(width * 0.3, (width - gap * (n - 1)) / n)
        x0 = left + (width - (bw * n + gap * (n - 1))) / 2
        back = BUTTON_DARK if self.dark else BUTTON_LIGHT
        for i, words in enumerate(choices):
            x = x0 + i * (bw + gap)
            border, thick = self._mark(i)
            self._box(x, bottom, bw, height, back, border, thickness=thick)
            text = words if words == str(i + 1) else '%d  %s' % (i + 1,
                                                                 words)
            label = self._text(text, x + bw / 2, bottom + height / 2,
                               min(calc_fontsize(14), height * 0.3))
            if label.content_width > bw * 0.9:
                label.font_size *= bw * 0.9 / label.content_width
            self.hits.append((x, bottom, bw, height,
                              lambda c=i: self.choose(c)))

    def _card(self, index: int, x, y, w, h, number: bool = True) -> None:
        """A clickable panel for choice *index*, numbered in its corner."""
        border, thick = self._mark(index)
        back = BUTTON_DARK if self.dark else (247, 248, 251)
        self._box(x, y, w, h, back, border, thickness=thick)
        if number:
            self._text(str(index + 1), x + 8, y + h - 8,
                       calc_fontsize(13), anchor='left', anchor_y='top',
                       bold=True)
        self.hits.append((x, y, w, h, lambda c=index: self.choose(c)))

    def _facts(self) -> str:
        if self.puzzle is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
