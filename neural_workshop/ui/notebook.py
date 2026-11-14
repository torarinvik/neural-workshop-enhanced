# -*- coding: utf-8 -*-
"""Notebook on screen: the card on the left, the notebook on the right.

A fact card shows its code and a Next button; every notebook line has a
Write button beside it that copies the card onto that line. A question
card shows the codes to choose from instead. The notebook stays in view
the whole time. :mod:`neural_workshop.notebook` deals the cards.

Keys: 1-4 answer, Shift+1-8 write onto a line, Enter next.

For the agent boundary: ports 0-3 choose answers, ports 4-11 write onto
lines 1-8, port 12 is Next.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import notebook as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

WRITE = model.MOST_CHOICES
NEXT = WRITE + model.MOST_LINES
PORTS = NEXT + 1

PAPER_LIGHT = (250, 246, 226)
PAPER_DARK = (58, 56, 46)
CARD_LIGHT = (232, 235, 240)
CARD_DARK = (46, 50, 58)
RULE = (150, 170, 210)
FADED = (140, 140, 140)


class Notebook(RungTask):
    """Remember what will be asked, with a few lines of paper to help."""

    instance: Optional['Notebook'] = None

    TITLE = 'Notebook'
    TASK_ID = 'notebook'
    PREFIX = 'NOTEBOOK'
    CATEGORY = 'long_term_memory'
    FEEDBACK = 2.5
    FOOTNOTE = _('Write: copy the card onto a line (Shift+1-8)   Next '
                 '(Enter)   answer 1-4   Esc: menu')

    def __init__(self) -> None:
        self.round: Optional[model.Round] = None
        self.last: Optional[bool] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.round = None
        self.last = None

    def _deal(self) -> bool:
        self.round = model.Round(model.deal(self.rung, rng=self.rng))
        self.last = None
        self.message = _('Keep what you will be asked for')
        return True

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if port < WRITE:
            self.answer(port)
        elif port < NEXT:
            self.write(port - WRITE)
        else:
            self.next()

    def write(self, line: int) -> None:
        if self.phase == self.PLAY and self.round.write(line):
            self._redraw()

    def next(self) -> None:
        if self.phase == self.PLAY and self.round.next():
            self._after()

    def answer(self, choice: int) -> None:
        if self.phase != self.PLAY:
            return
        right = self.round.answer(choice)
        if right is None:
            return
        self.last = right
        self._after()

    def _after(self) -> None:
        play = self.round
        if not play.over:
            self._redraw()
            return
        total = play.deal.questions
        self._judge(play.right == total,
                    _('%d of %d answered right') % (play.right, total))

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._8:
            if modifiers & key.MOD_SHIFT:
                self.write(symbol - key._1)
            else:
                self.answer(symbol - key._1)
        elif symbol in (key.RETURN, key.ENTER, key.N):
            self.next()

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        card_w = width * 0.46
        self._draw_card(left, bottom, card_w, height)
        gap = width * 0.04
        self._draw_notebook(left + card_w + gap, bottom,
                            width - card_w - gap, height)

    def _draw_card(self, left, bottom, width, height) -> None:
        play = self.round
        card = play.card
        back = CARD_DARK if self.dark else CARD_LIGHT
        ch = height * 0.5
        cy = bottom + height - ch
        self._box(left, cy, width, ch, back, self.ink)
        size = min(calc_fontsize(22), width * 0.05)
        if card is None:
            return
        self._text(_('card %d of %d') % (play.at + 1, len(play.deal.cards)),
                   left + 12, cy + ch - size * 0.9, size * 0.5,
                   anchor='left')
        words = card.words()
        colour = (*FADED, 255) if card.kind == 'noise' else None
        label = self._text(words, left + width / 2, cy + ch * 0.5, size,
                           bold=True, colour=colour)
        if label.content_width > width * 0.92:
            label.font_size *= width * 0.92 / label.content_width
        below = cy - height * 0.06
        bh = height * 0.13
        if card.kind == 'question':
            n = len(card.offered)
            bw = (width - (n - 1) * 10) / n
            for i, code in enumerate(card.offered):
                x = left + i * (bw + 10)
                self._box(x, below - bh, bw, bh, back, self.ink)
                words = self._text('%d: %d' % (i + 1, code), x + bw / 2,
                                   below - bh / 2,
                                   min(size * 0.8, bh * 0.4), bold=True)
                if words.content_width > bw * 0.85:
                    words.font_size *= bw * 0.85 / words.content_width
                self.hits.append((x, below - bh, bw, bh,
                                  lambda c=i: self.answer(c)))
        else:
            bw = width * 0.4
            x = left + (width - bw) / 2
            self._box(x, below - bh, bw, bh, back, self.ink)
            self._text(_('Next (Enter)'), x + bw / 2, below - bh / 2,
                       min(size * 0.7, bh * 0.4), bold=True)
            self.hits.append((x, below - bh, bw, bh, self.next))
        if self.last is not None and self.phase == self.PLAY:
            self._text(_('last answer: right') if self.last
                       else _('last answer: wrong'), left + width / 2,
                       below - bh - size, size * 0.55)

    def _draw_notebook(self, left, bottom, width, height) -> None:
        play = self.round
        paper = PAPER_DARK if self.dark else PAPER_LIGHT
        self._box(left, bottom, width, height, paper, self.ink)
        self._text(_('Notebook'), left + width / 2,
                   bottom + height - calc_fontsize(14),
                   calc_fontsize(14), bold=True)
        lines = play.lines
        top = bottom + height - calc_fontsize(14) * 2.4
        row = min((top - bottom) / max(len(lines), 1),
                  (top - bottom) / 5.0)
        size = min(calc_fontsize(16), row * 0.32)
        writable = play.card is not None and play.card.kind != 'question' \
            and self.phase == self.PLAY
        bw = width * 0.2
        for i, words in enumerate(lines):
            y = top - (i + 1) * row
            self.drawn.append(pyglet.shapes.Line(
                left + 8, y + 2, left + width - 8, y + 2, thickness=1,
                color=RULE, batch=self.batch, group=self.body_group))
            self._text('%d' % (i + 1), left + 14, y + row * 0.45, size * 0.8,
                       anchor='left', colour=(*FADED, 255))
            self._text(words, left + 14 + size * 2, y + row * 0.45, size,
                       anchor='left')
            if writable:
                x = left + width - bw - 10
                self._box(x, y + row * 0.15, bw, row * 0.62, None, self.ink)
                self._text(_('Write'), x + bw / 2, y + row * 0.46,
                           min(size * 0.8, row * 0.25))
                self.hits.append((x, y + row * 0.15, bw, row * 0.62,
                                  lambda l=i: self.write(l)))

    def _facts(self) -> str:
        play = self.round
        if play is None:
            return ''
        return (_('rung %d  %d/%d   questions %d of %d   right so far %d   '
                  '%d lines')
                % (self.rung, self.trial, self.total_trials,
                   len(play.answers), play.deal.questions, play.right,
                   len(play.lines)))
