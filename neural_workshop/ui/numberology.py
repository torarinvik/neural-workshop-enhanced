# -*- coding: utf-8 -*-
"""The Numberology sequence screen."""
from __future__ import annotations

import random
import time
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, from_top_edge, width_center
from ..i18n import _
from ..numberology import SequencePuzzle, generate, is_correct
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band


class Numberology:
    """Type the next term in a generated sequence."""

    instance: Optional['Numberology'] = None

    def __init__(self) -> None:
        if Numberology.instance is not None:
            Numberology.instance.close()
        self.rng = random.Random()
        self.clock = time.time
        self.puzzle: Optional[SequencePuzzle] = None
        self.typed = ''
        self.trial = 0
        self.results: List[Tuple[int, bool, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.difficulty = self.clamped(self.start_difficulty)
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_text,
                                   self.on_mouse_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Numberology.instance = self

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.NUMBEROLOGY)
        self.start_difficulty = int(opts['NUMBEROLOGY_LEVEL'])
        self.total_trials = int(opts['NUMBEROLOGY_TRIALS'])
        self.advance_on_perfect = bool(opts['NUMBEROLOGY_ADVANCE'])

    @staticmethod
    def clamped(value: int) -> int:
        return max(1, int(value))

    def _floor(self) -> float:
        return above_the_band(from_bottom_edge(52))

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.batch = pyglet.graphics.Batch()
        wide = state.window.width * 0.9
        self.title = pyglet.text.Label(_('Numberology'), font_size=calc_fontsize(22),
            weight='bold', color=(fg, fg, fg, 255), batch=self.batch,
            x=width_center(), y=from_top_edge(34), anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label('', font_size=calc_fontsize(13),
            color=(fg, fg, fg, 255), batch=self.batch, x=width_center(),
            y=from_top_edge(68), anchor_x='center', anchor_y='center',
            font_name=FONTLIST)
        self.sequence = pyglet.text.Label('', font_size=calc_fontsize(22),
            weight='bold', color=(fg, fg, fg, 255), batch=self.batch,
            x=width_center(), y=from_top_edge(190), anchor_x='center',
            anchor_y='center', font_name=FONTLIST, multiline=True,
            width=wide, align='center')
        self.hint = pyglet.text.Label('', font_size=calc_fontsize(13),
            color=(fg, fg, fg, 255), batch=self.batch, x=width_center(),
            y=from_top_edge(250), anchor_x='center', anchor_y='center',
            font_name=FONTLIST, multiline=True, width=wide, align='center')
        self.entry = pyglet.text.Label('', font_size=calc_fontsize(20),
            color=(0, 114, 178, 255), batch=self.batch, x=width_center(),
            y=max(self._floor() + 36, from_bottom_edge(150)), anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   type the answer   Enter: check'
              '   O: options'),
            font_size=calc_fontsize(11), color=(fg, fg, fg, 255), batch=self.batch,
            x=width_center(), y=from_bottom_edge(24), anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.puzzle = None
        self.typed = ''
        self.difficulty = self.clamped(self.start_difficulty)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def open_options(self) -> None:
        taskoptions.open_task_options('numberology', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.puzzle = generate(self.difficulty, self.rng.randrange(1 << 30))
        self.typed = ''
        self.verdict_shown = None
        self.verdict.clear()
        self.phase = 'working'
        self.message = _('Difficulty %d') % self.difficulty
        self._redraw()

    def _finish(self) -> None:
        perfect = (len(self.results) == self.total_trials and
                   bool(self.results) and
                   all(right for _difficulty, right, _time in self.results))
        if perfect and self.advance_on_perfect:
            self.start_difficulty = self.difficulty + 1
            state.cfg['NUMBEROLOGY_LEVEL'] = self.start_difficulty
            self.message = _('Perfect session — next level %d') % self.start_difficulty
        elif perfect:
            self.message = _('Perfect session — level %d') % self.difficulty
        else:
            right = sum(1 for _difficulty, ok, _time in self.results if ok)
            self.message = _('%d of %d correct — level stays at %d') % (
                right, self.total_trials, self.difficulty)
        self.phase = 'done'
        self._redraw()

    def write(self, character: str) -> None:
        if self.phase != 'working' or character not in '0123456789-':
            return
        if character == '-' and self.typed:
            return
        self.typed += character
        self._redraw()

    def erase(self) -> None:
        if self.phase == 'working' and self.typed:
            self.typed = self.typed[:-1]
            self._redraw()

    def submit(self) -> None:
        if self.phase != 'working' or not self.typed:
            return
        right = is_correct(self.puzzle, self.typed)
        self.results.append((self.difficulty, right, self.clock()))
        self.message = _('Right') if right else _('No — the answer was %s') % self.puzzle.answer
        self.verdict_shown = (right, _('Right') if right else _('No'))
        self.verdict.show(right, self.verdict_shown[1])
        self.phase = 'judged'
        self._redraw()

    def _redraw(self) -> None:
        self.status.text = self.message + (('     ' + _('question %d/%d') %
                            (self.trial, self.total_trials))
                          if self.phase == 'working' else '')
        self.sequence.text = (self.puzzle.asked if self.puzzle and
                              self.phase in ('working', 'judged') else '')
        self.hint.text = (self.puzzle.rule if self.phase == 'judged' and self.puzzle
                          else _('Find the rule, then type the next number.'))
        self.entry.text = (self.typed + ('_' if self.phase == 'working' else '')
                           if self.phase in ('working', 'judged') else '')

    def advance(self) -> None:
        if self.phase in ('ready', 'done'):
            self.start_run()
        elif self.phase == 'judged':
            self._next_trial()

    def close(self) -> None:
        if Numberology.instance is not self:
            return
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_text,
                                     self.on_mouse_press, self.on_draw)
        Numberology.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase != 'working':
            self.advance()
        elif symbol == key.O and self.phase != 'working':
            self.open_options()
        elif symbol in (key.ENTER, key.RETURN, key.NUM_ENTER):
            self.submit()
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.erase()
        return pyglet.event.EVENT_HANDLED

    def on_text(self, text: str) -> bool:
        for character in text:
            self.write(character)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> bool:
        self.advance()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['Numberology']
