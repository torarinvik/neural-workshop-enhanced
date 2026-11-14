# -*- coding: utf-8 -*-
"""Hidden Wiring: flip switches, look at the lamps, then make patterns.

On the left the switches, numbered, each a toggle that costs nothing to
flip. Above them the lamps, lettered, showing what the last look saw.
Look (L) shows the lamps for the switches as they stand and costs a
point; every look goes in the notebook on the right, switches as squares
and lamps as dots. Exam (E) starts the questions: the lamps show a
pattern wanted -- a ring for lit, a cross for dark -- and Answer (Enter)
gives the switches as they stand. Nothing is said until the last answer;
then the wiring is printed. :mod:`neural_workshop.wiring` has the
wirings, the ladder and the reference; this module draws them.

For the agent boundary: ports 0-7 flip switches 1-8, then Look, Exam
and Answer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Callable, Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, state, wiring as model
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

FEEDBACK = 4.0

#: Agent ports: flip switch 0-7, then these.
LOOK, EXAM, ANSWER = 8, 9, 10
PORTS = 11

LIT = (250, 204, 60)
UNLIT_LIGHT = (196, 200, 208)
UNLIT_DARK = (70, 74, 82)
ON = (60, 150, 90)
OFF_LIGHT = (232, 235, 240)
OFF_DARK = (46, 50, 58)
WANT = (40, 90, 220)
LETTERS = 'ABCDEF'


def gate_text(gate: model.Gate) -> str:
    names = [('not %d' if inv else '%d') % (i + 1)
             for i, inv in zip(gate.inputs, gate.inverted)]
    if gate.kind == 'copy':
        return names[0]
    if gate.kind == 'majority':
        return _('two of %s') % ', '.join(names)
    word = {'and': _(' and '), 'or': _(' or '), 'xor': _(' xor ')}
    return word[gate.kind].join(names)


class Wiring:
    """Learn the wiring for less than the reference paid."""

    instance: Optional['Wiring'] = None

    def __init__(self) -> None:
        if Wiring.instance is not None:
            Wiring.instance.close()
        self.rng = random.Random()
        self.clock = time.time
        self.round: Optional[model.Round] = None
        self.par = 0.0
        self.rung = 1
        self.trial = 0
        self.switches: List[bool] = []
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, float, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.reveal = ''
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
        Wiring.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.WIRING)
        self.start_rung = int(opts['WIRING_RUNG'])
        self.total_trials = int(opts['WIRING_TRIALS'])
        self.adaptive = bool(opts['WIRING_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('wiring', on_apply=self.apply_options)

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

        self.title = label(_('Hidden Wiring'), calc_fontsize(22),
                           from_top_edge(36), bold=True)
        self.status = label('', calc_fontsize(14), from_top_edge(70))
        self.facts = label('', calc_fontsize(12), from_top_edge(96))
        self.footnote = label(
            _('1-8: flip a switch   L: look   E: exam   Enter: answer   '
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
        self.reveal = ''

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
        self.switches = [False] * dealt.level.switches
        self.verdict_shown = None
        self.verdict.clear()
        self.reveal = ''
        self.phase = 'looking'
        self.message = _('Learn the wiring for %s or less') % \
            _points(self.par)
        self._redraw()

    @property
    def setting(self) -> int:
        return sum(1 << i for i, on in enumerate(self.switches) if on)

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if port < LOOK:
            self.flip(port)
        elif port == LOOK:
            self.look()
        elif port == EXAM:
            self.start_exam()
        elif port == ANSWER:
            self.answer()

    def flip(self, switch: int) -> None:
        if self.phase not in ('looking', 'examining') \
                or switch >= len(self.switches):
            return
        self.switches[switch] = not self.switches[switch]
        self._redraw()

    def look(self) -> None:
        if self.phase != 'looking':
            return
        if self.round.look(self.setting) is None:
            return
        if self.round.looks_left <= 0:
            self.start_exam()
            return
        self._redraw()

    def start_exam(self) -> None:
        if self.phase != 'looking':
            return
        self.round.start_exam()
        self.phase = 'examining'
        self.message = _('Set the switches for the pattern, then Answer')
        self._redraw()

    def answer(self) -> None:
        if self.phase != 'examining':
            return
        self.round.answer(self.setting)
        if self.round.over:
            self._judge()
        else:
            self._redraw()

    def _judge(self) -> None:
        play = self.round
        passed = play.cost <= self.par + 1e-9
        self.results.append((play.level.rung, passed, play.cost, self.par))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.feedback_until = self.clock() + FEEDBACK
        self.message = (_('%d looks, %d wrong: cost %s against a par of %s')
                        % (len(play.looks), play.wrong, _points(play.cost),
                           _points(round(self.par, 1))))
        self.reveal = '   '.join(
            '%s = %s' % (LETTERS[l], gate_text(gate))
            for l, gate in enumerate(play.deal.lamps))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.round = None
        tally = self.score()
        self.message = (_('%d of %d under par   highest rung passed %d')
                        % (tally['passed'], tally['trials'],
                           tally['best_rung']))
        self.reveal = ''
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

    def _box(self, x, y, w, h, colour, border=None, group=None) -> None:
        self.drawn.append(pyglet.shapes.Rectangle(
            x, y, w, h, color=colour, batch=self.batch,
            group=group or self.card_group))
        if border is not None:
            self.drawn.append(pyglet.shapes.Box(
                x, y, w, h, thickness=3, color=border, batch=self.batch,
                group=self.body_group))

    def _button(self, x, y, w, h, words, action) -> None:
        self._box(x, y, w, h, OFF_DARK if self.dark else OFF_LIGHT,
                  self.ink)
        self._text(words, x + w / 2, y + h / 2, h * 0.3, bold=True)
        self.hits.append((x, y, w, h, action))

    def _lamp(self, cx, cy, r, lit, ring=None) -> None:
        unlit = UNLIT_DARK if self.dark else UNLIT_LIGHT
        self.drawn.append(pyglet.shapes.Circle(
            cx, cy, r, color=LIT if lit else unlit, batch=self.batch,
            group=self.card_group))
        if ring is not None:
            self.drawn.append(pyglet.shapes.Arc(
                cx, cy, r * 1.25, thickness=4, color=ring,
                batch=self.batch, group=self.body_group))

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.round is not None and self.phase in ('looking', 'examining',
                                                     'judged'):
            left, bottom, width, height = self._area()
            split = left + width * 0.5
            self._draw_panel(left, bottom, split - left, height)
            self._draw_notebook(split + width * 0.03, bottom,
                                left + width - split - width * 0.03, height)
        self._update_labels()

    def _draw_panel(self, left, bottom, width, height) -> None:
        play = self.round
        level = play.level
        # Lamps along the top.
        lamps = level.lamps
        r = min(width / (lamps * 3.2), height * 0.08)
        lamp_y = bottom + height * 0.78
        if self.phase == 'examining':
            shown, want = None, play.question
        elif play.looks:
            shown, want = play.looks[-1][1], None
        else:
            shown, want = 0, None
        for l in range(lamps):
            cx = left + width * (l + 0.5) / lamps
            if want is not None:
                lit = bool(want >> l & 1)
                self._lamp(cx, lamp_y, r, lit, WANT)
                self._text(_('lit') if lit else _('dark'), cx,
                           lamp_y - r * 1.8, r * 0.45, bold=True)
            else:
                self._lamp(cx, lamp_y, r, bool(shown >> l & 1))
            self._text(LETTERS[l], cx, lamp_y + r * 1.7, r * 0.5, bold=True)
        if self.phase == 'examining':
            self._text(_('question %d of %d: make this pattern')
                       % (len(play.answers) + 1, len(play.deal.exam)),
                       left + width / 2, lamp_y + r * 2.6, r * 0.42)
        elif play.looks:
            self._text(_('last look'), left + width / 2,
                       lamp_y + r * 2.6, r * 0.42)
        # Switches below.
        n = level.switches
        side = min(width / (n * 1.35), height * 0.16)
        sy = bottom + height * 0.32
        for i in range(n):
            x = left + (width - n * side * 1.3) / 2 + i * side * 1.3
            on = self.switches[i]
            self._box(x, sy, side, side * 1.4,
                      ON if on else (OFF_DARK if self.dark else OFF_LIGHT),
                      self.ink)
            self._text(_('on') if on else _('off'), x + side / 2,
                       sy + side * 0.7, side * 0.25, bold=True)
            self._text(str(i + 1), x + side / 2, sy - side * 0.3,
                       side * 0.28)
            self.hits.append((x, sy, side, side * 1.4,
                              lambda s=i: self.flip(s)))
        if self.phase == 'judged':
            self._text(self.reveal, left + width / 2, bottom + height * 0.12,
                       min(calc_fontsize(12), width / max(20, len(self.reveal))
                           * 1.6), bold=True)
            return
        bw, bh = width * 0.3, height * 0.11
        y = bottom + height * 0.04
        if self.phase == 'looking':
            self._button(left + width * 0.15, y, bw, bh, _('Look (L)'),
                         self.look)
            self._button(left + width * 0.55, y, bw, bh, _('Exam (E)'),
                         self.start_exam)
        else:
            self._button(left + width * 0.35, y, bw, bh,
                         _('Answer (Enter)'), self.answer)

    def _draw_notebook(self, left, bottom, width, height) -> None:
        play = self.round
        level = play.level
        looks = play.looks
        top = bottom + height
        self._text(_('notebook: switches   lamps'), left, top - 12,
                   calc_fontsize(11), anchor='left')
        columns = 2
        rows_room = max(1, -(-model.budget(level) // columns))
        row = min((height - 30) / rows_room, 40)
        cell = row * 0.7
        col_w = width / columns
        for index, (setting, shown) in enumerate(looks):
            column, line = divmod(index, rows_room)
            x = left + column * col_w
            y = top - 30 - (line + 1) * row
            for i in range(level.switches):
                self._box(x + i * cell * 1.05, y, cell, cell,
                          ON if setting >> i & 1
                          else (OFF_DARK if self.dark else OFF_LIGHT),
                          group=self.body_group)
            lx = x + level.switches * cell * 1.05 + cell
            for l in range(level.lamps):
                self._lamp(lx + l * cell * 1.1 + cell / 2, y + cell / 2,
                           cell * 0.42, bool(shown >> l & 1))

    def _update_labels(self) -> None:
        self.status.text = self.message
        play = self.round
        if play is None or self.phase not in ('looking', 'examining',
                                              'judged'):
            self.facts.text = ''
            return
        level = play.level
        parts = [_('rung %d  %d/%d') % (level.rung, self.trial,
                                        self.total_trials),
                 _('looks %d (%d left)') % (len(play.looks),
                                           max(0, play.looks_left)),
                 _('wrong answer %d') % level.penalty]
        if level.noise:
            parts.append(_('a lamp lies on %d%% of looks')
                         % round(level.noise * 100))
        self.facts.text = '  '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Wiring.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        Wiring.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

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
            self.flip(symbol - key._1)
        elif symbol == key.L:
            self.look()
        elif symbol == key.E:
            self.start_exam()
        elif symbol in (key.RETURN, key.ENTER):
            self.answer()
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
