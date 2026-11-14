# -*- coding: utf-8 -*-
"""Forms: type what the card says into the form, with as few keys as can be.

The form is on the left, the card on the right. The field in focus has a
blue frame and a cursor. Type into it; Tab goes to the next field, Enter
sends the page. A list field shows the items that start with what has
been typed -- Up and Down move between them, and the one lit is chosen
when Tab or Enter leaves the field. Space ticks a checkbox; Up and Down
move a radio button. A page sent with a field a form can tell is wrong
comes back with that field in red. Every key costs one; clicking a field
to move to it costs one too. :mod:`neural_workshop.forms` has the forms,
the ladder and the reference; this module draws them.

For the agent boundary: forty-six ports, one per key -- a-z, 0-9, space,
@ . - /, then Backspace, Tab, Enter, Up and Down.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import string
import time
from typing import Callable, Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, forms as model, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

FEEDBACK = 3.0

#: One port per key, in this order.
KEYS: Tuple[str, ...] = (tuple(string.ascii_lowercase) + tuple(string.digits)
                         + tuple(model.SYMBOLS)
                         + (model.BACKSPACE, model.TAB, model.ENTER,
                            model.UP, model.DOWN))
PORTS = len(KEYS)

FOCUS = (40, 90, 220)
MARKED = (214, 64, 58)
BOX_LIGHT = (255, 255, 255)
BOX_DARK = (40, 44, 52)
PANEL_LIGHT = (236, 239, 244)
PANEL_DARK = (30, 34, 40)
PICK = (196, 216, 250)
#: List items shown under a list field at most.
SHOWN = 6


class Forms:
    """Fill the form right, in no more keys than par."""

    instance: Optional['Forms'] = None

    def __init__(self) -> None:
        if Forms.instance is not None:
            Forms.instance.close()
        self.rng = random.Random()
        self.clock = time.time
        self.form: Optional[model.Form] = None
        self.par = 0.0
        self.rung = 1
        self.trial = 0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, float, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.reveal: List[str] = []
        self.drawn: List[object] = []
        self.hits: List[Tuple[float, float, float, float,
                              Callable[[], None]]] = []
        self._read_options()
        self.message = _('Press Space or click to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_text,
                                   self.on_mouse_press, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        Forms.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.FORMS)
        self.start_rung = int(opts['FORMS_RUNG'])
        self.total_trials = int(opts['FORMS_TRIALS'])
        self.adaptive = bool(opts['FORMS_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('forms', on_apply=self.apply_options)

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

        self.title = label(_('Forms'), calc_fontsize(22), from_top_edge(36),
                           bold=True)
        self.status = label('', calc_fontsize(14), from_top_edge(70))
        self.facts = label('', calc_fontsize(12), from_top_edge(96))
        self.footnote = label(
            _('type   Tab: next field   Enter: send   Up/Down: lists and '
              'radios   Space: tick   Esc: menu'),
            calc_fontsize(11), from_bottom_edge(26))
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
        self.form = None
        self.phase = 'ready'
        self.message = _('Press Space or click to start')
        self.verdict_shown = None
        self.reveal = []

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
        self.form = model.Form(dealt)
        self.par = model.par(dealt)
        self.verdict_shown = None
        self.verdict.clear()
        self.reveal = []
        self.phase = 'filling'
        self.message = _('Fill in the form in %s keys or fewer') % \
            _points(self.par)
        self._redraw()

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if 0 <= port < PORTS:
            self.press(KEYS[port])

    def press(self, which: str) -> None:
        if self.phase != 'filling':
            return
        self.form.press(which)
        if self.form.sent:
            self._judge()
        else:
            self._redraw()

    def focus_on(self, index: int) -> None:
        """A click on a field: it takes the focus, for one key."""
        if self.phase != 'filling':
            return
        form = self.form
        form._leave()
        form.keys += 1
        form.focus = index
        self._redraw()

    def _judge(self) -> None:
        form = self.form
        wrong = form.wrong
        passed = not wrong and form.cost <= self.par + 1e-9
        self.results.append((form.level.rung, passed, form.cost, self.par))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.feedback_until = self.clock() + FEEDBACK
        if wrong:
            self.message = _('Sent with %d wrong: %s') % (
                len(wrong), ', '.join(f.label for f in wrong))
            self.reveal = ['%s: %s' % (f.label, _shown_answer(f))
                           for f in wrong]
        else:
            self.message = (_('All right in %s keys against a par of %s')
                            % (_points(form.cost), _points(self.par)))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.form = None
        tally = self.score()
        self.message = (_('%d of %d right and under par   highest rung '
                          'passed %d') % (tally['passed'], tally['trials'],
                                          tally['best_rung']))
        self.reveal = []
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

    def _text(self, words, x, y, size, anchor='left', bold=False,
              colour=None) -> None:
        self.drawn.append(pyglet.text.Label(
            words, font_size=max(6.0, size), x=x, y=y, anchor_x=anchor,
            anchor_y='center', color=colour or self.textcolor,
            weight='bold' if bold else 'normal', batch=self.batch,
            group=self.text_group, font_name=FONTLIST))

    def _box(self, x, y, w, h, colour, border=None, group=None,
             thickness=2) -> None:
        self.drawn.append(pyglet.shapes.Rectangle(
            x, y, w, h, color=colour, batch=self.batch,
            group=group or self.card_group))
        if border is not None:
            self.drawn.append(pyglet.shapes.Box(
                x, y, w, h, thickness=thickness, color=border,
                batch=self.batch, group=self.body_group))

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.form is not None and self.phase in ('filling', 'judged'):
            left, bottom, width, height = self._area()
            split = left + width * 0.58
            self._draw_form(left, bottom, split - left - width * 0.02,
                            height)
            self._draw_card(split + width * 0.02, bottom,
                            left + width - split - width * 0.02, height)
        self._update_labels()

    def _draw_form(self, left, bottom, width, height) -> None:
        form = self.form
        panel = PANEL_DARK if self.dark else PANEL_LIGHT
        box = BOX_DARK if self.dark else BOX_LIGHT
        self._box(left, bottom, width, height, panel, self.ink)
        shown = form.visible()
        focus = form.field
        top = bottom + height
        size = calc_fontsize(12)
        pages = form.level.pages
        if pages > 1:
            self._text(_('Page %d of %d') % (form.page + 1, pages),
                       left + width - 12, top - size * 1.4, size * 0.9,
                       anchor='right')
        rows = max(1, len(shown)) + 1
        row = min((height - size * 3) / rows, size * 5.2)
        y = top - size * 2.6
        label_w = width * 0.36
        for index, field in enumerate(shown):
            y_mid = y - row / 2
            if field.kind != 'check':
                self._text(field.label, left + 14, y_mid, size)
            if field.hint:
                self._text('(%s)' % field.hint, left + 14,
                           y_mid - size * 1.3, size * 0.75,
                           colour=(*(150, 154, 162), 255))
            fx = left + label_w
            fw = width - label_w - 18
            fh = min(row * 0.62, size * 2.6)
            fy = y_mid - fh / 2
            frame = (MARKED if field.key in form.marked
                     else FOCUS if field is focus else self.ink)
            thick = 3 if frame != self.ink else 1
            kind = field.kind
            if kind == 'check':
                # A checkbox goes before its words, as on any form.
                side = fh * 0.8
                bx = left + 14
                self._box(bx, y_mid - side / 2, side, side, box, frame,
                          thickness=thick)
                if form.values[field.key]:
                    self._text('✓', bx + side / 2, y_mid, side * 0.5,
                               anchor='center', bold=True)
                self._text(field.label, bx + side * 1.4, y_mid, size)
            elif kind == 'radio':
                gap = fw / len(field.options)
                for i, option in enumerate(field.options):
                    cx = fx + i * gap + fh * 0.3
                    self.drawn.append(pyglet.shapes.Circle(
                        cx, y_mid, fh * 0.28, color=frame if i ==
                        form.values[field.key] else (150, 154, 162),
                        batch=self.batch, group=self.body_group))
                    self._text(option, cx + fh * 0.45, y_mid, size * 0.9)
            else:
                self._box(fx, fy, fw, fh, box, frame, thickness=thick)
                if kind == 'choice':
                    value = form.values[field.key]
                    words = (form.query[field.key] if field is focus
                             or value is None else field.options[value])
                else:
                    words = str(form.values[field.key])
                if field is focus and self.phase == 'filling':
                    words += '|'
                self._text(words, fx + 8, y_mid, size)
            self.hits.append((left, y - row, width, row,
                              lambda i=index: self.focus_on(i)))
            y -= row
        # A list field in focus shows what matches below the form's
        # rows, so it never hides another field.
        if focus is not None and focus.kind == 'choice' \
                and form.query[focus.key] and self.phase == 'filling':
            found = form.choices(focus)
            lit = min(form.lit[focus.key], max(0, len(found) - 1))
            first = max(0, lit - SHOWN + 1)
            item_h = size * 1.8
            lx = left + label_w
            lw = width - label_w - 18
            ly = y - size * 0.4
            for n, i in enumerate(found[first:first + SHOWN]):
                iy = ly - (n + 1) * item_h
                if iy < bottom + 4:
                    break
                self._box(lx, iy, lw, item_h,
                          PICK if first + n == lit else box, self.ink,
                          group=self.body_group, thickness=1)
                self._text(focus.options[i], lx + 8, iy + item_h / 2,
                           size * 0.9)
            if not found:
                self._text(_('no match'), lx + 8, ly - item_h / 2,
                           size * 0.9, colour=(*MARKED, 255))
        if self.reveal:
            for n, line in enumerate(self.reveal[:4]):
                self._text(_('should be ') + line, left + 14,
                           bottom + size * (1.5 + 1.6 * n), size * 0.9,
                           colour=(*MARKED, 255))

    def _draw_card(self, left, bottom, width, height) -> None:
        form = self.form
        panel = PANEL_DARK if self.dark else (252, 246, 220)
        self._box(left, bottom, width, height, panel, self.ink)
        lines = form.deal.card
        size = calc_fontsize(12)
        # Shrink until the longest line fits the card.
        longest = max(lines, key=len) if lines else ''
        probe = pyglet.text.Label(longest, font_size=size,
                                  font_name=FONTLIST)
        room = width - 28
        while probe.content_width > room and size > 7:
            size -= 0.5
            probe.font_size = size
        probe.delete()
        line = min(size * 2.0, (height - size * 3) / max(1, len(lines)))
        self._text(_('The card'), left + 14, bottom + height - size * 1.4,
                   size, bold=True)
        for n, words in enumerate(lines):
            self._text(words, left + 14,
                       bottom + height - size * 3.2 - n * line, size)

    def _update_labels(self) -> None:
        self.status.text = self.message
        form = self.form
        if form is None or self.phase not in ('filling', 'judged'):
            self.facts.text = ''
            return
        level = form.level
        parts = [_('rung %d  %d/%d') % (level.rung, self.trial,
                                        self.total_trials),
                 _('keys %d') % form.keys,
                 _('a page sent back costs %d') % level.penalty]
        if form.bounced:
            parts.append(_('sent back %d') % form.bounced)
        self.facts.text = '  '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Forms.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_text,
                                     self.on_mouse_press, self.on_draw)
        self._clear_drawn()
        Forms.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='computer')

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
        elif self.phase == 'filling':
            named = {key.BACKSPACE: model.BACKSPACE, key.TAB: model.TAB,
                     key.RETURN: model.ENTER, key.ENTER: model.ENTER,
                     key.UP: model.UP, key.DOWN: model.DOWN}
            if symbol in named:
                self.press(named[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_text(self, text: str) -> bool:
        if self.phase != 'filling':
            return pyglet.event.EVENT_HANDLED
        for char in text:
            if char.isalnum() or char in model.SYMBOLS:
                self.press(char)
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


def _shown_answer(field: model.Field) -> str:
    if field.kind in ('choice', 'radio'):
        return field.options[field.answer]
    if field.kind == 'check':
        return _('ticked') if field.answer else _('not ticked')
    return str(field.answer)


def _points(value: float) -> str:
    return ('%d' % value) if float(value).is_integer() else ('%.1f' % value)
