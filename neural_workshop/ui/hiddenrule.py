# -*- coding: utf-8 -*-
"""Hidden Rule: test objects under a lamp, then sit an exam on the rule.

On the left is the builder: one row per property in play, each showing
the object as it would be with that value, and the object as it stands
with a Test button beside it. Click a swatch to change the object;
click Test, or press T, to put it under the lamp, which costs a point.
On the right is the notebook: every object tested, on a yellow card if
it lit the lamp and a grey one if it did not, starting with the two
free examples. When you think you have the rule press Exam: objects
not seen before come up one at a time, and each must be called lit
(Y) or dark (N). Nothing is said until the last one, and every wrong
call costs the rung's penalty. :mod:`neural_workshop.hiddenrule` has
the rules, the ladder and the reference; this module draws them.

When the round is judged the rule is printed, so a round lost teaches
what a round won proves.

For the agent boundary the builder is steered: six ports each step one
property to its next value, which costs nothing, then Test, Exam, Lit
and Dark.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, hiddenrule as rules, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Seconds the verdict and the rule stay up before the next round.
FEEDBACK = 3.0

#: Agent ports: step property 0-5, then these.
TEST, EXAM, LIT, DARK = 6, 7, 8, 9
PORTS = 10

COLOURS = ((214, 64, 58), (52, 110, 220), (54, 160, 80), (226, 170, 30))
LIT_CARD = (252, 226, 120)
DARK_CARD_LIGHT = (176, 180, 188)
DARK_CARD_DARK = (70, 74, 82)
BLANK_LIGHT = (232, 235, 240)
BLANK_DARK = (46, 50, 58)
PICKED = (40, 90, 220)

#: What an object is when a property is not in play.
DEFAULTS = (1, 0, 1, 0, 0, 0)


def value_names() -> Tuple[Tuple[str, ...], ...]:
    return ((_('red'), _('blue'), _('green'), _('gold')),
            (_('circle'), _('square'), _('triangle'), _('diamond')),
            (_('small'), _('large')),
            (_('one'), _('two'), _('three')),
            (_('solid'), _('hollow')),
            (_('no bar'), _('barred')))


def property_names() -> Tuple[str, ...]:
    return (_('colour'), _('shape'), _('size'), _('count'), _('fill'),
            _('bar'))


def atom_text(atom: rules.Atom) -> str:
    feature, value, positive = atom
    word = value_names()[feature][value]
    return word if positive else _('not %s') % word


def describe(rule: rules.Rule) -> str:
    """The rule in words."""
    words = [atom_text(atom) for atom in rule.atoms]
    form = rule.form
    if form == 'is':
        return words[0]
    if form == 'both':
        return _('%s and %s') % tuple(words)
    if form == 'either':
        return _('%s or %s') % tuple(words)
    if form == 'one_of':
        return _('%s or %s, not both') % tuple(words)
    if form == 'all':
        return _('%s, %s and %s') % tuple(words)
    if form == 'any':
        return _('%s, %s or %s') % tuple(words)
    if form == 'two_of':
        return _('at least two of %s, %s, %s') % tuple(words)
    if form == 'both_or':
        return _('(%s and %s) or %s') % tuple(words)
    return _('(%s or %s) and %s') % tuple(words)


def full_item(item: Sequence[int]) -> Tuple[int, ...]:
    return tuple(item) + DEFAULTS[len(item):]


def draw_object(batch, groups, cx: float, cy: float, span: float,
                item: Sequence[int], back: Tuple[int, int, int],
                ink: Tuple[int, int, int], into: List[object]) -> None:
    """Draw *item* centred in a square of side *span*."""
    colour, shape, size, count, fill, bar = full_item(item)
    body, hole = groups
    paint = COLOURS[colour]
    radius = span * (0.16 if size else 0.09)
    copies = count + 1
    gap = span * 0.3
    for copy in range(copies):
        x = cx + (copy - (copies - 1) / 2.0) * gap
        y = cy + span * 0.04
        _shape(batch, body, shape, x, y, radius, paint, into)
        if fill:
            _shape(batch, hole, shape, x, y, radius * 0.5, back, into)
    if bar:
        into.append(pyglet.shapes.Rectangle(
            cx - span * 0.36, cy - span * 0.34, span * 0.72, span * 0.05,
            color=ink, batch=batch, group=body))


def _shape(batch, group, shape: int, x: float, y: float, r: float,
           colour, into: List[object]) -> None:
    if shape == 0:
        into.append(pyglet.shapes.Circle(x, y, r, color=colour,
                                         batch=batch, group=group))
    elif shape == 1:
        side = r * 1.7
        into.append(pyglet.shapes.Rectangle(x - side / 2, y - side / 2,
                                            side, side, color=colour,
                                            batch=batch, group=group))
    elif shape == 2:
        into.append(pyglet.shapes.Triangle(x - r, y - r * 0.8, x + r,
                                           y - r * 0.8, x, y + r,
                                           color=colour, batch=batch,
                                           group=group))
    else:
        into.append(pyglet.shapes.Polygon(
            (x, y + r * 1.1), (x + r * 1.1, y), (x, y - r * 1.1),
            (x - r * 1.1, y), color=colour, batch=batch, group=group))


class HiddenRule:
    """Find the rule for less than the reference paid."""

    instance: Optional['HiddenRule'] = None

    def __init__(self) -> None:
        if HiddenRule.instance is not None:
            HiddenRule.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.round: Optional[rules.Round] = None
        self.par = 0.0
        self.rung = 1
        self.trial = 0
        self.item: List[int] = []
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, float, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.reveal = ''
        self.drawn: List[object] = []
        self.hits: List[Tuple[float, float, float, float,
                              Callable[[], None]]] = []
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        HiddenRule.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.HIDDEN_RULE)
        self.start_rung = int(opts['HIDDEN_RULE_RUNG'])
        self.total_trials = int(opts['HIDDEN_RULE_TRIALS'])
        self.adaptive = bool(opts['HIDDEN_RULE_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('hidden_rule',
                                      on_apply=self.apply_options)

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
        self.hole_group = pyglet.graphics.Group(order=2)
        self.text_group = pyglet.graphics.Group(order=3)

        def label(words, size, y, bold=False):
            return pyglet.text.Label(
                words, font_size=size, color=self.textcolor,
                weight='bold' if bold else 'normal', batch=self.batch,
                x=width_center(), y=y, anchor_x='center',
                anchor_y='center', font_name=FONTLIST)

        self.title = label(_('Hidden Rule'), calc_fontsize(22),
                           from_top_edge(36), bold=True)
        self.status = label('', calc_fontsize(14), from_top_edge(70))
        self.facts = label('', calc_fontsize(12), from_top_edge(96))
        self.footnote = label(
            _('click a swatch to change it   T: test   E: exam   '
              'Y / N: lit or dark   Esc: menu'),
            calc_fontsize(12), from_bottom_edge(26))
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _area(self) -> Tuple[float, float, float, float]:
        """Left, bottom, width and height of the playing area."""
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
        self.message = _('Press Space to start')
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
        dealt = rules.deal(self.rung, rng=self.rng)
        self.round = rules.Round(dealt)
        self.par = rules.par(dealt)
        self.item = [0] * len(dealt.level.values)
        self.verdict_shown = None
        self.verdict.clear()
        self.reveal = ''
        self.phase = 'testing'
        self.message = _('Learn the rule for %s or less') % \
            _points(self.par)
        self._redraw()

    @property
    def notebook(self) -> List[Tuple[int, bool]]:
        if self.round is None:
            return []
        return list(self.round.deal.seeds) + list(self.round.tests)

    def index_of(self, item: Sequence[int]) -> int:
        return rules.space(self.round.level).items.index(tuple(item))

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        """One agent port: step a property, or test, exam, lit, dark."""
        if self.round is None:
            return
        if port < TEST:
            self.step(port)
        elif port == TEST:
            self.test()
        elif port == EXAM:
            self.start_exam()
        elif port == LIT:
            self.answer(True)
        elif port == DARK:
            self.answer(False)

    def step(self, feature: int, value: Optional[int] = None) -> None:
        if self.phase != 'testing' or feature >= len(self.item):
            return
        count = self.round.level.values[feature]
        self.item[feature] = ((self.item[feature] + 1) % count
                              if value is None else value % count)
        self._redraw()

    def test(self) -> None:
        if self.phase != 'testing':
            return
        if self.round.test(self.index_of(self.item)) is None:
            return
        if self.round.tests_left <= 0:
            self.start_exam()
            return
        self._redraw()

    def start_exam(self) -> None:
        if self.phase != 'testing':
            return
        self.round.start_exam()
        self.phase = 'examining'
        self.message = _('Lit or dark? Nothing is said until the end')
        self._redraw()

    def answer(self, call: bool) -> None:
        if self.phase != 'examining':
            return
        self.round.answer(call)
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
        self.message = (_('%d tests, %d wrong: cost %s against a par of %s')
                        % (len(play.tests), play.wrong, _points(play.cost),
                           _points(self.par)))
        self.reveal = _('The rule was: %s') % describe(play.deal.rule)
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
            'mean_cost': (sum(r[2] for r in self.results) / trials
                          if trials else 0.0),
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

    def _card(self, x: float, y: float, w: float, h: float, colour,
              border=None) -> None:
        self.drawn.append(pyglet.shapes.Rectangle(
            x, y, w, h, color=colour, batch=self.batch,
            group=self.card_group))
        if border is not None:
            self.drawn.append(pyglet.shapes.Box(
                x, y, w, h, thickness=3, color=border, batch=self.batch,
                group=self.body_group))

    def _button(self, x: float, y: float, w: float, h: float, words: str,
                action: Callable[[], None], colour=None) -> None:
        self._card(x, y, w, h, colour or (BLANK_DARK if self.dark
                                          else BLANK_LIGHT), self.ink)
        self._text(words, x + w / 2, y + h / 2, h * 0.3, bold=True)
        self.hits.append((x, y, w, h, action))

    def _object(self, item, x: float, y: float, span: float,
                back) -> None:
        draw_object(self.batch, (self.body_group, self.hole_group),
                    x + span / 2, y + span / 2, span, item, back,
                    self.ink, self.drawn)

    def _redraw(self) -> None:
        self._clear_drawn()
        play = self.round
        if self.phase in ('testing', 'examining', 'judged') and play:
            left, bottom, width, height = self._area()
            split = left + width * 0.42
            self._draw_notebook(split + width * 0.03, bottom,
                                left + width - split - width * 0.03, height)
            if self.phase == 'testing':
                self._draw_builder(left, bottom, split - left, height)
            elif self.phase == 'examining':
                self._draw_exam(left, bottom, split - left, height)
            else:
                self._text(self.reveal, left + (split - left) / 2,
                           bottom + height / 2, calc_fontsize(14),
                           bold=True)
        self._update_labels()

    def _draw_builder(self, left, bottom, width, height) -> None:
        level = self.round.level
        back = BLANK_DARK if self.dark else BLANK_LIGHT
        names = property_names()
        rows = len(level.values) + 2
        row = height / rows
        span = min(row * 0.9, width * 0.16)
        label_w = width * 0.22
        for feature, count in enumerate(level.values):
            y = bottom + height - (feature + 1) * row + (row - span) / 2
            self._text(names[feature], left + label_w - 8, y + span / 2,
                       span * 0.2, anchor='right')
            for value in range(count):
                x = left + label_w + value * (span * 1.1)
                variant = list(self.item)
                variant[feature] = value
                picked = self.item[feature] == value
                self._card(x, y, span, span, back,
                           PICKED if picked else None)
                self._object(variant, x, y, span, back)
                self.hits.append((x, y, span, span,
                                  lambda f=feature, v=value: self.step(f, v)))
        big = min(row * 1.8, width * 0.3)
        y = bottom + (row * 2 - big) / 2
        x = left + label_w
        self._card(x, y, big, big, back, self.ink)
        self._object(self.item, x, y, big, back)
        bw, bh = width * 0.22, big * 0.36
        self._button(x + big + width * 0.05, y + big - bh, bw, bh,
                     _('Test (T)'), self.test)
        self._button(x + big + width * 0.05, y, bw, bh, _('Exam (E)'),
                     self.start_exam)

    def _draw_exam(self, left, bottom, width, height) -> None:
        play = self.round
        back = BLANK_DARK if self.dark else BLANK_LIGHT
        big = min(height * 0.5, width * 0.6)
        x = left + (width - big) / 2
        y = bottom + height * 0.32
        self._text(_('question %d of %d') % (len(play.answers) + 1,
                                             len(play.deal.exam)),
                   left + width / 2, y + big + height * 0.06,
                   calc_fontsize(13))
        self._card(x, y, big, big, back, self.ink)
        item = rules.space(play.level).items[play.question]
        self._object(item, x, y, big, back)
        bw, bh = width * 0.36, height * 0.14
        gap = width * 0.06
        self._button(left + width / 2 - bw - gap / 2, bottom + height * 0.08,
                     bw, bh, _('Lit (Y)'), lambda: self.answer(True),
                     LIT_CARD)
        self._button(left + width / 2 + gap / 2, bottom + height * 0.08,
                     bw, bh, _('Dark (N)'), lambda: self.answer(False),
                     DARK_CARD_DARK if self.dark else DARK_CARD_LIGHT)

    def _draw_notebook(self, left, bottom, width, height) -> None:
        play = self.round
        items = rules.space(play.level).items
        notes = self.notebook
        capacity = 2 + play.level.budget
        columns = 10
        rows = (capacity + columns - 1) // columns
        span = min(width / columns, height * 0.86 / rows)
        top = bottom + height
        self._text(_('notebook   (yellow: lit   grey: dark)'), left,
                   top - span * 0.25, span * 0.18, anchor='left')
        dark_card = DARK_CARD_DARK if self.dark else DARK_CARD_LIGHT
        for slot, (index, shown) in enumerate(notes):
            column, line = slot % columns, slot // columns
            x = left + column * span
            y = top - span * 0.55 - (line + 1) * span
            card = LIT_CARD if shown else dark_card
            pad = span * 0.05
            self._card(x + pad, y + pad, span - 2 * pad, span - 2 * pad,
                       card)
            self._object(items[index], x + pad, y + pad, span - 2 * pad,
                         card)

    def _update_labels(self) -> None:
        self.status.text = self.message
        play = self.round
        if play is None or self.phase not in ('testing', 'examining',
                                              'judged'):
            self.facts.text = ''
            return
        level = play.level
        parts = [_('rung %d  %d/%d') % (level.rung, self.trial,
                                        self.total_trials),
                 _('tests %d (cost 1 each, %d left)')
                 % (len(play.tests), play.tests_left),
                 _('wrong answer %s') % _points(level.penalty)]
        if level.noise:
            parts.append(_('lamp lies %d%%') % round(level.noise * 100))
        self.facts.text = '  '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if HiddenRule.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        HiddenRule.instance = None

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
        elif key._1 <= symbol <= key._6:
            self.step(symbol - key._1)
        elif symbol == key.T:
            self.test()
        elif symbol == key.E:
            self.start_exam()
        elif symbol == key.Y:
            self.answer(True)
        elif symbol == key.N:
            self.answer(False)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if button != mouse.LEFT:
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
