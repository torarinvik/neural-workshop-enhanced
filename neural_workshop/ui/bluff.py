# -*- coding: utf-8 -*-
"""Bluff: one card each, check or bet, fold or call -- and read the other.

Your card is in the middle, the opponent's face down above it until a
showdown turns it over. What has been done this hand is written between
them. Two buttons: Check or Bet when it is yours to open, Fold or Call
when you face a bet. On the right, the last hands: both cards where they
were shown, what each did, and what it won. That log is how the opponent
is read. :mod:`neural_workshop.bluff` has the game, the opponents and the
reference; this module draws them.

For the agent boundary: port 0 checks or folds, port 1 bets or calls.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Callable, Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import bluff as model, display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

FEEDBACK = 3.0
PASSIVE, AGGRESSIVE = model.PASSIVE, model.AGGRESSIVE
PORTS = 2

CARD = (252, 250, 244)
BACK = (52, 90, 160)
BUTTON_LIGHT = (232, 235, 240)
BUTTON_DARK = (46, 50, 58)
WON = (60, 150, 90)
LOST = (214, 64, 58)
#: Hands shown in the log.
LOG = 12


def said(actions: str, player_first: bool) -> List[str]:
    """The hand in words, one line per action."""
    out = []
    for i, act in enumerate(actions):
        who = _('You') if (i % 2 == 0) == player_first else _('They')
        verb = {'c': _('check'), 'b': _('bet'), 'k': _('call'),
                'f': _('fold')}[act]
        out.append('%s %s' % (who, verb))
    return out


class Bluff:
    """Read the opponent well enough to beat par."""

    instance: Optional['Bluff'] = None

    def __init__(self) -> None:
        if Bluff.instance is not None:
            Bluff.instance.close()
        self.rng = random.Random()
        self.clock = time.time
        self.match: Optional[model.Match] = None
        self.par = 0.0
        self.rung = 1
        self.trial = 0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, float, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.drawn: List[object] = []
        self.hits: List[Tuple[float, float, float, float,
                              Callable[[], None]]] = []
        self._read_options()
        self.message = _('Press Space or click to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        Bluff.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.BLUFF)
        self.start_rung = int(opts['BLUFF_RUNG'])
        self.total_trials = int(opts['BLUFF_TRIALS'])
        self.adaptive = bool(opts['BLUFF_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('bluff', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        self.dark = bool(state.cfg.BLACK_BACKGROUND)
        fg = 255 if self.dark else 0
        self.textcolor = (fg, fg, fg, 255)
        self.ink = (fg, fg, fg)
        self.batch = pyglet.graphics.Batch()
        self.card_group = pyglet.graphics.Group(order=0)
        self.body_group = pyglet.graphics.Group(order=1)
        self.text_group = pyglet.graphics.Group(order=3)

        def label(words, size, y, bold=False):
            return pyglet.text.Label(
                words, font_size=size, color=self.textcolor,
                weight='bold' if bold else 'normal', batch=self.batch,
                x=width_center(), y=y, anchor_x='center',
                anchor_y='center', font_name=FONTLIST)

        self.title = label(_('Bluff'), calc_fontsize(22), from_top_edge(36),
                           bold=True)
        self.status = label('', calc_fontsize(14), from_top_edge(70))
        self.facts = label('', calc_fontsize(12), from_top_edge(96))
        self.footnote = label(
            _('1 or K: check / fold   2 or B: bet / call   Esc: menu'),
            calc_fontsize(12), from_bottom_edge(26))
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _area(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(116)
        bottom = above_the_band(from_bottom_edge(58))
        width = window.width * 0.92
        return ((window.width - width) / 2.0, bottom, width,
                max(40.0, top - bottom))

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.match = None
        self.phase = 'ready'
        self.message = _('Press Space or click to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self.rung = max(1, self.start_rung)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        dealt = model.deal(self.rung, rng=self.rng)
        self.match = model.Match(dealt)
        self.par = model.par(dealt)
        self.verdict_shown = None
        self.verdict.clear()
        self.phase = 'playing'
        self.message = _('Play %d hands worth %s or more') % (
            dealt.level.hands, _points(round(self.par, 1)))
        self._redraw()

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if port in (PASSIVE, AGGRESSIVE):
            self.act(port)

    def act(self, choice: int) -> None:
        if self.phase != 'playing':
            return
        if not self.match.act(choice):
            return
        if self.match.over:
            self._judge()
        else:
            self._redraw()

    def _judge(self) -> None:
        match = self.match
        passed = match.value >= self.par - 1e-9
        self.results.append((match.level.rung, passed, match.value,
                             self.par))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.feedback_until = self.clock() + FEEDBACK
        kinds = ' then '.join(kind for _h, kind in match.deal.kinds)
        self.message = (_('Your play was worth %s against a par of %s '
                          '(chips %+d) -- they were: %s')
                        % (_points(round(match.value, 1)),
                           _points(round(self.par, 1)), match.chips, kinds))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.match = None
        tally = self.score()
        self.message = (_('%d of %d at par or better   highest rung passed '
                          '%d') % (tally['passed'], tally['trials'],
                                   tally['best_rung']))
        self._redraw()

    def score(self) -> Dict[str, float]:
        trials = len(self.results)
        return {
            'trials': trials,
            'passed': sum(1 for r in self.results if r[1]),
            'best_rung': max((r[0] for r in self.results if r[1]),
                             default=0),
        }

    def update(self, dt: float) -> None:
        if self.phase == 'judged' and self.clock() >= self.feedback_until:
            self._next_trial()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []
        self.hits = []

    def _text(self, words, x, y, size, anchor='center', bold=False,
              colour=None) -> None:
        self.drawn.append(pyglet.text.Label(
            words, font_size=max(6.0, size), x=x, y=y, anchor_x=anchor,
            anchor_y='center', color=colour or self.textcolor,
            weight='bold' if bold else 'normal', batch=self.batch,
            group=self.text_group, font_name=FONTLIST))

    def _box(self, x, y, w, h, colour, border=None) -> None:
        self.drawn.append(pyglet.shapes.Rectangle(
            x, y, w, h, color=colour, batch=self.batch,
            group=self.card_group))
        if border is not None:
            self.drawn.append(pyglet.shapes.Box(
                x, y, w, h, thickness=3, color=border, batch=self.batch,
                group=self.body_group))

    def _card(self, x, y, w, h, value: Optional[int]) -> None:
        if value is None:
            self._box(x, y, w, h, BACK, self.ink)
            return
        self._box(x, y, w, h, CARD, self.ink)
        self._text(str(value + 1), x + w / 2, y + h / 2, h * 0.4,
                   bold=True, colour=(20, 20, 20, 255))

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.match is not None and self.phase in ('playing', 'judged'):
            left, bottom, width, height = self._area()
            split = left + width * 0.56
            self._draw_table(left, bottom, split - left, height)
            self._draw_log(split + width * 0.03, bottom,
                           left + width - split - width * 0.03, height)
        self._update_labels()

    def _draw_table(self, left, bottom, width, height) -> None:
        match = self.match
        cards = match.level.cards
        ch = min(height * 0.26, width * 0.22)
        cw = ch * 0.7
        cx = left + width / 2
        size = calc_fontsize(13)
        self._text(_('cards run from 1 to %d') % cards, cx,
                   bottom + height - size, size * 0.85)
        hand = match.hand
        if hand is None:
            return
        # The opponent's card, face down.
        self._card(cx - cw / 2, bottom + height - ch - size * 2, cw, ch,
                   None)
        self._text(_('them'), cx + cw, bottom + height - ch / 2 - size * 2,
                   size, anchor='left')
        # What has happened this hand.
        lines = said(match.actions, hand.player_first) or \
            [_('You open') if hand.player_first else _('They open')]
        mid = bottom + height * 0.5
        for n, words in enumerate(lines):
            self._text(words, cx, mid + size * 1.6 * (len(lines) / 2 - n),
                       size, bold=True)
        # Yours.
        self._card(cx - cw / 2, bottom + height * 0.18, cw, ch,
                   hand.player)
        self._text(_('you'), cx + cw, bottom + height * 0.18 + ch / 2,
                   size, anchor='left')
        if self.phase != 'playing' or not match.player_to_act():
            return
        facing = match.actions in ('b', 'cb')
        words = ((_('Fold (1)'), _('Call (2)')) if facing
                 else (_('Check (1)'), _('Bet (2)')))
        bw, bh = width * 0.3, height * 0.11
        y = bottom + height * 0.02
        for n, choice in enumerate((PASSIVE, AGGRESSIVE)):
            x = cx - bw - width * 0.03 if n == 0 else cx + width * 0.03
            self._box(x, y, bw, bh, BUTTON_DARK if self.dark
                      else BUTTON_LIGHT, self.ink)
            self._text(words[n], x + bw / 2, y + bh / 2, bh * 0.32,
                       bold=True)
            self.hits.append((x, y, bw, bh,
                              lambda c=choice: self.act(c)))

    def _draw_log(self, left, bottom, width, height) -> None:
        match = self.match
        size = calc_fontsize(11)
        top = bottom + height
        self._text(_('last hands   you / them'), left, top - size,
                   size, anchor='left', bold=True)
        records = match.records[-LOG:]
        row = min(size * 2.4, (height - size * 3) / LOG)
        for n, record in enumerate(reversed(records)):
            y = top - size * 3 - n * row
            theirs = '?' if record.shown is None else str(record.shown + 1)
            moves = ', '.join(said(record.actions, record.player_first))
            self._text('%d / %s' % (record.player_card + 1, theirs), left,
                       y, size, anchor='left', bold=True)
            self._text(moves.lower(), left + size * 5, y, size * 0.85,
                       anchor='left')
            self._text('%+d' % record.won, left + width, y, size,
                       anchor='right', bold=True,
                       colour=(*(WON if record.won > 0 else LOST), 255))

    def _update_labels(self) -> None:
        self.status.text = self.message
        match = self.match
        if match is None or self.phase not in ('playing', 'judged'):
            self.facts.text = ''
            return
        level = match.level
        parts = [_('rung %d  %d/%d') % (level.rung, self.trial,
                                        self.total_trials),
                 _('hand %d of %d') % (min(match.index + 1, level.hands),
                                       level.hands),
                 _('chips %+d') % match.chips]
        self.facts.text = '  '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Bluff.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        Bluff.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='decisions')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif self.phase in ('ready', 'done'):
            if symbol == key.SPACE:
                self.start_run()
            elif symbol == key.C:
                self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in (key._1, key.K, key.F):
            self.act(PASSIVE)
        elif symbol in (key._2, key.B, key.C):
            self.act(AGGRESSIVE)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if button != mouse.LEFT:
            return pyglet.event.EVENT_HANDLED
        if self.phase in ('ready', 'done'):
            self.start_run()
            return pyglet.event.EVENT_HANDLED
        for left, bottom, w, h, action in list(self.hits):
            if left <= x <= left + w and bottom <= y <= bottom + h:
                action()
                break
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def _points(value: float) -> str:
    return ('%d' % value) if float(value).is_integer() else ('%.1f' % value)
