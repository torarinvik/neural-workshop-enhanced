# -*- coding: utf-8 -*-
"""Multiple-choice verbal reasoning from the local Verbal IQ corpus."""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from ..verbal import DatasetUnavailable, Question, QuestionBank
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

MINE = (0, 114, 178)


class VerbalReasoning:
    """Read a question and select the answer it supports."""

    instance: Optional['VerbalReasoning'] = None

    def __init__(self) -> None:
        if VerbalReasoning.instance is not None:
            VerbalReasoning.instance.close()
        self.rng = random.Random()
        self.clock = time.time
        self.bank = QuestionBank()  # no path lookup or Parquet import yet
        self.question: Optional[Question] = None
        self.choice = 0
        self.answered: Optional[int] = None
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[bool, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.message = _('Press Space to load the first question')
        self.options: List[pyglet.text.Label] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        VerbalReasoning.instance = self

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.VERBAL_REASONING)
        self.total_trials = int(opts['VERBAL_REASONING_TRIALS'])
        self.show_explanation = bool(opts['VERBAL_REASONING_EXPLANATION'])

    def open_options(self) -> None:
        taskoptions.open_task_options('verbal_reasoning',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    def _floor(self) -> float:
        return above_the_band(from_bottom_edge(54))

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        wide = int(state.window.width * 0.90)
        self.title = pyglet.text.Label(
            _('Verbal Reasoning'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch, x=width_center(),
            y=from_top_edge(32), anchor_x='center', anchor_y='center',
            font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(62),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.prompt = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(90),
            anchor_x='center', anchor_y='top', font_name=FONTLIST,
            multiline=True, width=wide, align='left')
        self.note = pyglet.text.Label(
            '', font_size=calc_fontsize(10), color=self.textcolor,
            batch=self.batch, x=width_center(), y=self._floor() + 6,
            anchor_x='center', anchor_y='bottom', font_name=FONTLIST,
            multiline=True, width=wide, align='center')
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start/next   arrows: choose'
              '   Enter: answer   O: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._build_options()
        self._redraw()

    def _build_options(self) -> None:
        self.options = []
        if self.question is None:
            return
        width = int(state.window.width * 0.86)
        for number, answer in enumerate(self.question.choices):
            self.options.append(pyglet.text.Label(
                '%d. %s' % (number + 1, answer),
                font_size=calc_fontsize(10), color=self.textcolor,
                batch=self.batch, x=width_center(), y=0,
                anchor_x='center', anchor_y='top', font_name=FONTLIST,
                multiline=True, width=width, align='left'))

    def relayout(self) -> None:
        self._build_chrome()

    def _reset(self) -> None:
        self.question = None
        self.choice = 0
        self.answered = None
        self.trial = 0
        self.results = []
        self.phase = 'ready'
        self.message = _('Press Space to load the first question')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        try:
            made = self.bank.draw(self.rng)
        except DatasetUnavailable as exc:
            self.question = None
            self.phase = 'unavailable'
            self.message = str(exc)
            self._build_chrome()
            return
        self.trial += 1
        self.question = made
        self.choice = 0
        self.answered = None
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'asking'
        self.message = made.task_type.replace('_', ' ').title()
        self._build_chrome()

    def move(self, step: int) -> None:
        if self.phase == 'asking' and self.question is not None:
            self.choice = (self.choice + step) % len(self.question.choices)
            self._redraw()

    def submit(self) -> None:
        if self.phase == 'asking':
            self.choose(self.choice)

    def choose(self, number: int) -> None:
        if self.phase != 'asking' or self.question is None:
            return
        if not 0 <= int(number) < len(self.question.choices):
            return
        self.choice = int(number)
        right = self.choice == self.question.answer
        self.answered = self.choice
        self.results.append((right, self.clock() - self.started_at))
        self.message = (_('Right') if right else
                        _('No — it was "%s"') % self.question.answer_text)
        self.verdict_shown = (right, self.message)
        self.verdict.show(right, _('Right') if right else _('No'))
        self.phase = 'judged'
        self._redraw()

    def _finish(self) -> None:
        self.question = None
        self.phase = 'done'
        self.message = _('%d of %d right') % (
            sum(1 for right, _seconds in self.results if right),
            len(self.results))
        self._build_chrome()

    def score(self) -> Dict[str, int]:
        return {'asked': len(self.results),
                'right': sum(1 for right, _seconds in self.results if right),
                'seconds': int(sum(seconds for _right, seconds in self.results))}

    def _redraw(self) -> None:
        question = self.question
        self.prompt.text = question.prompt if question is not None else ''
        length = len(self.prompt.text)
        self.prompt.font_size = calc_fontsize(12 if length < 600 else
                                             10 if length < 1000 else 8)
        if question is not None and self.phase == 'judged' and self.show_explanation:
            explanation = question.explanation.strip()
            self.note.text = explanation[:600] + ('…' if len(explanation) > 600 else '')
        else:
            self.note.text = ''
        self._lay_out()
        for number, label in enumerate(self.options):
            picked = self.answered if self.phase == 'judged' else self.choice
            label.color = MINE + (255,) if number == picked else self.textcolor
        parts = [self.message]
        if question is not None and self.phase == 'asking':
            parts.append(_('question %d/%d') % (self.trial, self.total_trials))
        self.status.text = '     '.join(parts)

    def _lay_out(self) -> None:
        top = self.prompt.y - self.prompt.content_height - calc_fontsize(12)
        bottom = self._floor() + 8
        if self.note.text:
            bottom += self.note.content_height + calc_fontsize(8)
        count = max(1, len(self.options))
        step = max(calc_fontsize(22), (top - bottom) / count)
        for number, label in enumerate(self.options):
            label.font_size = min(calc_fontsize(10), max(7.0, step * 0.30))
            label.y = top - number * step

    def close(self) -> None:
        if VerbalReasoning.instance is not self:
            return
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        VerbalReasoning.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    def advance(self) -> None:
        if self.phase in ('ready', 'done', 'unavailable'):
            self.start_run()
        elif self.phase == 'judged':
            self._next_trial()

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol == key.O and self.phase != 'asking':
            self.open_options()
        elif symbol == key.SPACE and self.phase != 'asking':
            self.advance()
        elif self.phase == 'asking':
            if symbol in (key.DOWN, key.RIGHT):
                self.move(1)
            elif symbol in (key.UP, key.LEFT):
                self.move(-1)
            elif symbol in (key.ENTER, key.RETURN, key.NUM_ENTER, key.SPACE):
                self.submit()
            elif key._1 <= symbol <= key._5:
                self.choose(symbol - key._1)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase != 'asking':
            self.advance()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['VerbalReasoning']
