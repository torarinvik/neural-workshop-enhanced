# -*- coding: utf-8 -*-
"""Triage on screen: cards along the top, the open one below.

Each card shows what it pays and its row of digits (or, face down, how
many digits and a question mark). Click a card or press its number to
open it; below, the open row is drawn large with a swap button between
every pair of neighbours. Done (Enter) ends the round with what is left.
:mod:`neural_workshop.triage` has the rules and the reference.

For the agent boundary: ports 0-7 open cards 1-8, ports 8-15 swap the
open row's digits 1-2, 2-3, ... 8-9, and port 16 is Done.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import triage as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

SWAP = model.MOST_CARDS
DONE = SWAP + model.LONGEST - 1
PORTS = DONE + 1

CARD_LIGHT = (232, 235, 240)
CARD_DARK = (46, 50, 58)
OPEN = (40, 90, 220)
SOLVED = (60, 170, 90)
FACE_DOWN = (120, 128, 150)


class Triage(RungTask):
    """Spend a budget of moves on the puzzles worth it."""

    instance: Optional['Triage'] = None

    TITLE = 'Triage'
    TASK_ID = 'triage'
    PREFIX = 'TRIAGE'
    CATEGORY = 'decisions'
    FOOTNOTE = _('click a card or press 1-8 to open it   click a swap '
                 'button between digits   Enter: done   Esc: menu')

    def __init__(self) -> None:
        self.round: Optional[model.Round] = None
        self.par = 0.0
        super().__init__()

    def _clear_trial(self) -> None:
        self.round = None

    def _deal(self) -> bool:
        dealt = model.deal(self.rung, rng=self.rng)
        self.round = model.Round(dealt)
        self.par = model.par(dealt)
        self.message = _('Earn %s or more with %d moves') % (
            _points(self.par), dealt.budget)
        return True

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if port < SWAP:
            self.open_card(port)
        elif port < DONE:
            self.swap(port - SWAP)
        else:
            self.done()

    def open_card(self, index: int) -> None:
        if self.phase == self.PLAY and self.round.open_card(index):
            self._after()

    def swap(self, at: int) -> None:
        if self.phase == self.PLAY and self.round.swap(at):
            self._after()

    def done(self) -> None:
        if self.phase == self.PLAY:
            self.round.done()
            self._after()

    def _after(self) -> None:
        play = self.round
        if not play.over:
            self._redraw()
            return
        passed = play.value >= self.par - 1e-9
        self._judge(passed, _('Earned %d against a par of %s   (the best '
                              'possible was %d)')
                    % (play.value, _points(self.par), model.best(play.deal)))

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._8:
            self.open_card(symbol - key._1)
        elif symbol in (key.RETURN, key.ENTER):
            self.done()

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        play = self.round
        dealt = play.deal
        count = len(dealt.cards)
        per_row = min(count, 4)
        rows = (count + per_row - 1) // per_row
        gap = width * 0.015
        top_h = height * 0.5
        cw = (width - gap * (per_row - 1)) / per_row
        ch = (top_h - gap * (rows - 1)) / rows
        back = CARD_DARK if self.dark else CARD_LIGHT
        size = min(calc_fontsize(14), ch * 0.16, cw * 0.07)
        for index, card in enumerate(dealt.cards):
            r, c = divmod(index, per_row)
            x = left + c * (cw + gap)
            y = bottom + height - (r + 1) * ch - r * gap
            border = (SOLVED if index in play.solved else
                      OPEN if index == play.open else self.ink)
            self._box(x, y, cw, ch, back, border,
                      thickness=4 if border != self.ink else 2)
            self._text('%d' % (index + 1), x + 10, y + ch - size * 1.2,
                       size, anchor='left', bold=True)
            self._text(_('pays %d') % card.pays, x + cw / 2,
                       y + ch * 0.75, size * 1.1, bold=True)
            if index in play.solved:
                words = _('solved')
            elif index in play.turned:
                words = ' '.join(str(d) for d in play.rows[index])
            else:
                words = _('%d digits, face down') % len(card.row)
            self._text(words, x + cw / 2, y + ch * 0.42, size * 1.15,
                       colour=None if index in play.turned
                       or index in play.solved else (*FACE_DOWN, 255))
            if self.phase == 'judged':
                self._text(_('cost %d') % card.cost, x + cw / 2,
                           y + ch * 0.14, size * 0.9)
            self.hits.append((x, y, cw, ch,
                              lambda i=index: self.open_card(i)))
        self._draw_open(left, bottom, width, height * 0.44, back)

    def _draw_open(self, left, bottom, width, height, back) -> None:
        play = self.round
        bw, bh = width * 0.14, height * 0.2
        bx = left + width - bw
        self._box(bx, bottom, bw, bh, back, self.ink)
        self._text(_('Done (Enter)'), bx + bw / 2, bottom + bh / 2,
                   min(calc_fontsize(13), bh * 0.35), bold=True)
        self.hits.append((bx, bottom, bw, bh, self.done))
        if play.open is None:
            self._text(_('Open a card to work on it'), left + width / 2,
                       bottom + height * 0.6, calc_fontsize(14))
            return
        row = play.rows[play.open]
        n = len(row)
        cell = min(width * 0.8 / (n * 1.5), height * 0.45)
        total = n * cell + (n - 1) * cell * 0.5
        x0 = left + (width - total) / 2
        y = bottom + height * 0.45
        for j, digit in enumerate(row):
            x = x0 + j * cell * 1.5
            self._box(x, y, cell, cell, back, OPEN)
            self._text(str(digit), x + cell / 2, y + cell / 2, cell * 0.45,
                       bold=True)
            if j < n - 1:
                sx = x + cell
                sw = cell * 0.5
                self._box(sx + 2, y + cell * 0.25, sw - 4, cell * 0.5,
                          None, self.ink)
                self._text('<>', sx + sw / 2, y + cell / 2, cell * 0.16)
                self.hits.append((sx, y, sw, cell,
                                  lambda a=j: self.swap(a)))
        self._text(_('card %d: %d swaps still to go')
                   % (play.open + 1, model.inversions(row)),
                   left + width / 2, y - cell * 0.35, calc_fontsize(12))

    def _facts(self) -> str:
        play = self.round
        if play is None:
            return ''
        return (_('rung %d  %d/%d   moves left %d of %d   earned %d   '
                  'par %s')
                % (self.rung, self.trial, self.total_trials,
                   play.moves_left, play.deal.budget, play.value,
                   _points(self.par)))


def _points(value: float) -> str:
    return ('%d' % value) if float(value).is_integer() else ('%.1f' % value)
