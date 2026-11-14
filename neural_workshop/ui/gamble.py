# -*- coding: utf-8 -*-
"""Gamble: pull levers, find the machine that pays, and know when to stop.

A row of slot machines. Each card says what a win pays (and, where pulls
cost, the price of a pull); below it is the strip of that machine's last
results -- green for a win, grey for nothing, red for a bite -- and how
often it has been pulled. Click a machine or press its number to pull
it. Where pulls cost, S walks away with what is left. That strip is all
there is to go on: the odds are hidden, and on the higher rungs they
move. :mod:`neural_workshop.gamble` has the machines, the ladder and the
reference; this module draws them.

When the round is judged each machine's true average at the end is
shown, so a round lost shows where the money was.

For the agent boundary: ports 0-7 pull machines 1-8, port 8 stops.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Callable, Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, gamble as model, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Seconds the verdict stays up before the next round.
FEEDBACK = 3.0

#: Agent ports: pull machine 0-7, then stop.
STOP = model.MOST_ARMS
PORTS = model.MOST_ARMS + 1

WIN = (60, 170, 90)
NOTHING = (150, 154, 162)
BITE = (214, 64, 58)
CARD_LIGHT = (232, 235, 240)
CARD_DARK = (46, 50, 58)
LAST = (40, 90, 220)
#: Results shown under a machine.
STRIP = 12


class Gamble:
    """Pull well enough to beat par."""

    instance: Optional['Gamble'] = None

    def __init__(self) -> None:
        if Gamble.instance is not None:
            Gamble.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.round: Optional[model.Round] = None
        self.par = 0.0
        self.rung = 1
        self.trial = 0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, float, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.reveal = False
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
        Gamble.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.GAMBLE)
        self.start_rung = int(opts['GAMBLE_RUNG'])
        self.total_trials = int(opts['GAMBLE_TRIALS'])
        self.adaptive = bool(opts['GAMBLE_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('gamble', on_apply=self.apply_options)

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

        self.title = label(_('Gamble'), calc_fontsize(22),
                           from_top_edge(36), bold=True)
        self.status = label('', calc_fontsize(14), from_top_edge(70))
        self.facts = label('', calc_fontsize(12), from_top_edge(96))
        self.footnote = label(
            _('click a machine or press 1-8 to pull it   S: stop   '
              'Esc: menu'),
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
        self.round = None
        self.phase = 'ready'
        self.message = _('Press Space or click to start')
        self.verdict_shown = None
        self.reveal = False

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
        self.round = model.Round(dealt)
        self.par = model.par(dealt)
        self.verdict_shown = None
        self.verdict.clear()
        self.reveal = False
        self.phase = 'pulling'
        self.message = _('Make your pulls worth %s or more') % \
            _points(self.par)
        self._redraw()

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        """One agent port: pull a machine, or stop."""
        if port == STOP:
            self.stop()
        else:
            self.pull(port)

    def pull(self, arm: int) -> None:
        if self.phase != 'pulling':
            return
        if self.round.pull(arm) is None:
            return
        if self.round.over:
            self._judge()
        else:
            self._redraw()

    def stop(self) -> None:
        if self.phase != 'pulling':
            return
        if self.round.stop():
            self._judge()

    def _judge(self) -> None:
        play = self.round
        passed = not play.bust and play.value >= self.par - 1e-9
        self.results.append((play.level.rung, passed, play.value, self.par))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.feedback_until = self.clock() + FEEDBACK
        if play.bust:
            self.message = _('Bust: the bankroll ran dry')
        else:
            self.message = (_('Your pulls were worth %s against a par of %s'
                              '   (coins won %d)')
                            % (_points(round(play.value, 1)),
                               _points(round(self.par, 1)), play.total))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)
        self.reveal = True
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.round = None
        tally = self.score()
        self.message = (_('%d of %d at par or better   highest rung passed '
                          '%d') % (tally['passed'], tally['trials'],
                                   tally['best_rung']))
        self.reveal = False
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

    def _text(self, words: str, x: float, y: float, size: float,
              anchor: str = 'center', bold: bool = False,
              colour=None) -> None:
        self.drawn.append(pyglet.text.Label(
            words, font_size=max(6.0, size), x=x, y=y, anchor_x=anchor,
            anchor_y='center', color=colour or self.textcolor,
            weight='bold' if bold else 'normal', batch=self.batch,
            group=self.text_group, font_name=FONTLIST))

    def _box(self, x, y, w, h, colour, border=None, group=None) -> None:
        self.drawn.append(pyglet.shapes.Rectangle(
            x, y, w, h, color=colour, batch=self.batch,
            group=group or self.card_group))
        if border is not None:
            self.drawn.append(pyglet.shapes.Box(
                x, y, w, h, thickness=3, color=border, batch=self.batch,
                group=self.body_group))

    def _redraw(self) -> None:
        self._clear_drawn()
        play = self.round
        if play is not None and self.phase in ('pulling', 'judged'):
            self._draw_machines(*self._area())
        self._update_labels()

    def _draw_machines(self, left, bottom, width, height) -> None:
        play = self.round
        level = play.level
        arms = level.arms
        gap = width * 0.015
        w = min((width - gap * (arms - 1)) / arms, height * 0.7)
        x0 = left + (width - (w * arms + gap * (arms - 1))) / 2
        # The bottom strip is left for Stop, inside the playing area.
        h = height * 0.84
        y = bottom + height * 0.12
        back = CARD_DARK if self.dark else CARD_LIGHT
        last = play.history[-1][0] if play.history else None
        size = min(calc_fontsize(13), w * 0.075)
        for arm in range(arms):
            x = x0 + arm * (w + gap)
            machine = play.deal.machines[arm]
            self._box(x, y, w, h, back, LAST if arm == last else self.ink)
            top = y + h
            self._text(_('Machine %d') % (arm + 1) if w > 160 else '%d' % (arm + 1), x + w / 2,
                       top - h * 0.07, size * 1.15, bold=True)
            self._text(_('pays %d') % machine.pays, x + w / 2,
                       top - h * 0.16, size)
            if level.price:
                self._text(_('costs %d') % level.price, x + w / 2,
                           top - h * 0.23, size)
            seen = play.seen(arm)
            self._text(_('pulled %d') % len(seen), x + w / 2,
                       top - h * 0.32, size)
            if seen:
                gross = [won + level.price for won in seen]
                wins = sum(1 for g in gross if g > 0)
                self._text(_('won %d of %d') % (wins, len(seen)),
                           x + w / 2, top - h * 0.40, size)
                worst = min(gross)
                if worst < 0:
                    self._text(_('once lost %d') % -worst, x + w / 2,
                               top - h * 0.48, size, colour=(*BITE, 255))
            # The strip of recent results, newest at the bottom.
            recent = seen[-STRIP:]
            cell = min(w * 0.7 / 4, h * 0.4 / 3)
            for index, won in enumerate(recent):
                row, column = divmod(index, 4)
                gross = won + level.price
                colour = WIN if gross > 0 else BITE if gross < 0 else NOTHING
                self._box(x + w * 0.15 + column * cell,
                          y + h * 0.47 - (row + 1) * cell * 1.05,
                          cell * 0.85, cell * 0.85, colour,
                          group=self.body_group)
            if self.reveal:
                t = min(play.t, level.pulls - 1)
                truth = model.worth(play.deal, t, arm)
                self._text(_('%+.2f a pull') % truth, x + w / 2,
                           y + h * 0.05, size, bold=True)
            elif self.phase == 'pulling':
                self._text(_('pull (%d)') % (arm + 1), x + w / 2,
                           y + h * 0.05, size, bold=True)
            self.hits.append((x, y, w, h, lambda a=arm: self.pull(a)))
        if level.price and self.phase == 'pulling':
            bw, bh = max(w * 0.9, width * 0.12), height * 0.09
            bx = left + (width - bw) / 2
            self._box(bx, bottom, bw, bh, back, self.ink)
            self._text(_('Stop (S)'), bx + bw / 2, bottom + bh / 2, size,
                       bold=True)
            self.hits.append((bx, bottom, bw, bh, self.stop))

    def _update_labels(self) -> None:
        self.status.text = self.message
        play = self.round
        if play is None or self.phase not in ('pulling', 'judged'):
            self.facts.text = ''
            return
        level = play.level
        parts = [_('rung %d  %d/%d') % (level.rung, self.trial,
                                        self.total_trials),
                 _('pulls left %d') % play.pulls_left,
                 _('coins %+d') % play.total]
        if level.bankroll:
            parts.append(_('bankroll %d') % (level.bankroll + play.total))
        if level.drift or level.jumps:
            parts.append(_('the odds move'))
        self.facts.text = '  '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Gamble.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        Gamble.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='decisions')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif key._1 <= symbol <= key._8:
            self.pull(symbol - key._1)
        elif symbol == key.S:
            self.stop()
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
