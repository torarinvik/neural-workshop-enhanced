# -*- coding: utf-8 -*-
"""The scramble screen: a corrupted line above, what you make of it below.

The reasoning lives in :mod:`neural_workshop.scramble` and the text in
:mod:`neural_workshop.sentences`; this module is the two lines drawn
and the keys that fill the second one. Four decisions matter here:

* **You type the whole sentence, not one word at a time.** Filling in
  a word at a time would need boxes, and boxes would say how many
  words there are and how long each one is — which above rung five is
  most of the answer, because that is exactly the rung where the
  spaces stop being where the words are. One free line gives nothing
  away. It costs more typing, and that is the trade.

* **The pointer starts a run and nothing else.** Both word games grew
  a mouse because a board and a grid are places; a line of text is
  not. Every affordance that suggested itself here — click a word to
  mark it done, click to copy its letters up — was a second game
  rather than a second way to play this one, so there is none. Click
  to start, click to go on, and type.

* **How many readings the letters allow is printed.** It is measured
  rather than guessed (:attr:`~neural_workshop.scramble.Deal.ambiguity`)
  and it is the honest description of a rung: at the bottom the
  letters allow one sentence and the work is seeing it, at the top
  they allow ten to the twenty-seventh and the work is knowing which.
  It gives nothing away — it is a count of what is *not* determined.

* **A wrong answer is shown the sentence.** The verdict carries the
  line that was there. Without it the hard rungs teach nothing at
  all: you would be told you were wrong about a sentence you never
  got to read.

SPDX-License-Identifier: GPL-2.0-or-later
"""
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
from ..scramble import GRADES, Deal, correct, generate, grade_of, normalise
from ..sentences import have, missing_message
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: What the player has typed, as against the corrupted line above it.
MINE = (0, 114, 178)           # blue
LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def readings(deal: Deal) -> str:
    """How many sentences the letters alone still allow.

    Rounded hard and hedged where it should be: once the spaces move,
    the count is measured on word boundaries the player cannot see, so
    it is a floor and the line says *at least*.
    """
    floor = deal.grade.spaces > 0
    if deal.ambiguity < 0.05:
        return (_('at least one reading fits the letters') if floor
                else _('one reading fits the letters'))
    if deal.ambiguity < 5:
        count = int(round(10 ** deal.ambiguity))
        return (_('at least %d readings fit the letters') % count if floor
                else _('about %d readings fit the letters') % count)
    power = int(round(deal.ambiguity))
    return (_('at least 10^%d readings fit the letters') % power if floor
            else _('about 10^%d readings fit the letters') % power)


class Scramble:
    """Read the corrupted line, type what it said. Enter checks it."""

    instance: Optional['Scramble'] = None

    def __init__(self) -> None:
        if Scramble.instance is not None:
            Scramble.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.deal: Optional[Deal] = None
        self.typed = ''
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, bool, float]] = []   # rung, right, secs
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.message = _('Press Space to start')
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Scramble.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SCRAMBLE)
        self.start_rung = int(opts['SCRAMBLE_LEVEL'])
        self.total_trials = int(opts['SCRAMBLE_TRIALS'])
        self.show_count = bool(opts['SCRAMBLE_SHOW_COUNT'])
        self.adaptive = bool(opts['SCRAMBLE_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    @staticmethod
    def stocked() -> bool:
        """Whether the fetched text is there, as against the seed."""
        return have()

    def open_options(self) -> None:
        taskoptions.open_task_options('scramble', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _floor(self) -> float:
        """Nothing this task draws goes below here.

        The typed line is blue, and blue on a pale page has a rim of
        every blend between the two — part of which is a verdict
        colour, whatever the middle of the letter is. So the guard is
        the geometry and not the palette, and the tests assert this
        rather than trusting a sweep to notice.
        """
        return above_the_band(from_bottom_edge(52))

    def _lines(self) -> Tuple[float, float]:
        """Where the corrupted line sits, and where the typed one does."""
        top = from_top_edge(116)
        bottom = self._floor()
        height = max(60.0, top - bottom)
        return bottom + height * 0.60, bottom + height * 0.28

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        wide = state.window.width * 0.88
        self.title = pyglet.text.Label(
            _('Scramble'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(64),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.note = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(90),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        scrambled, answer = self._lines()
        self.line = pyglet.text.Label(
            '', font_size=calc_fontsize(21), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=scrambled, anchor_x='center',
            anchor_y='center', font_name=FONTLIST, multiline=True,
            width=wide, align='center')
        self.entry = pyglet.text.Label(
            '', font_size=calc_fontsize(17), color=MINE + (255,),
            batch=self.batch, x=width_center(), y=answer,
            anchor_x='center', anchor_y='center', font_name=FONTLIST,
            multiline=True, width=wide, align='center')
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   type the line   Enter: check'
              '   O: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour; tests/check_band.py is what says nothing else
        # this task draws puts a saturated colour in the bottom quarter.
        # Rebuilt with the chrome, so a verdict already up is put back.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.deal = None
        self.typed = ''
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        made = generate(self.rung, seed=self.rng.randrange(1 << 30))
        if made is None:
            # No sentence of this shape to draw on. With the seed text
            # that is a real state and not a crash, and saying so beats
            # dealing something from the wrong rung and calling it this
            # one.
            self.phase = 'done'
            self.message = _('No sentence at this level')
            self._redraw()
            return
        self.deal = made
        self.typed = ''
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'reading'
        self.message = _(grade_of(self.rung).name)
        self._redraw()

    # --- playing ---------------------------------------------------------

    def write(self, letter: str) -> None:
        """Add one letter to the answer."""
        if self.phase != 'reading' or letter not in LETTERS:
            return
        self.typed += letter
        self._redraw()

    def space(self) -> None:
        """Add a word break. Refused at the front and after another."""
        if self.phase != 'reading' or not self.typed.strip():
            return
        if self.typed.endswith(' '):
            return
        self.typed += ' '
        self._redraw()

    def erase(self) -> None:
        if self.phase != 'reading' or not self.typed:
            return
        self.typed = self.typed[:-1]
        self._redraw()

    def submit(self) -> None:
        """Mark the answer. Refused while it is empty."""
        if self.phase != 'reading' or not normalise(self.typed):
            return
        self._judge()

    def _judge(self) -> None:
        took = self.clock() - self.started_at
        right = correct(self.deal, self.typed)
        self.results.append((self.rung, right, took))
        # The sentence goes up whether or not it was got. Told only
        # that they were wrong, a player has read a corrupted line for
        # a minute and learned nothing from it.
        self.message = (_('Right — %s') % self.deal.answer if right
                        else _('No — it was: %s') % self.deal.answer)
        if self.adaptive:
            self.rung = self.clamped(self.rung + (1 if right else -1))
        self.verdict_shown = (right, self.message)
        self.verdict.show(right, _('Right') if right else _('No'))
        self.phase = 'judged'
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d of %d right, highest level %d') % (
            tally['right'], tally['asked'], tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        return {
            'asked': len(self.results),
            'right': sum(1 for _r, right, _t in self.results if right),
            'best_rung': max((rung for rung, right, _t in self.results
                              if right), default=0),
            'seconds': int(sum(took for _r, _s, took in self.results)),
        }

    # --- drawing ---------------------------------------------------------

    def _redraw(self) -> None:
        scrambled, answer = self._lines()
        self.line.y, self.entry.y = scrambled, answer
        if self.deal is not None and self.phase in ('reading', 'judged'):
            self.line.text = self.deal.shown
            self.note.text = (readings(self.deal) if self.phase == 'reading'
                              else '')
        else:
            self.line.text = ''
            self.note.text = ''
        if self.phase == 'reading':
            self.entry.text = self.typed + '_'
        elif self.phase == 'judged':
            self.entry.text = self.typed
        else:
            self.entry.text = ''
        self._update_status()

    def _update_status(self) -> None:
        parts = [self.message]
        if self.deal is not None and self.phase == 'reading':
            said = _('line %d/%d') % (self.trial, self.total_trials)
            if self.show_count:
                said += _('   %d words') % len(self.deal.words)
            parts.append(said)
        if self.phase == 'ready' and not self.stocked():
            parts.append(missing_message())
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Scramble.instance is not self:
            return
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        Scramble.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    def advance(self) -> None:
        """Whatever Space or a click means in the phase we are in."""
        if self.phase in ('ready', 'done'):
            self.start_run()
        elif self.phase == 'judged':
            self._next_trial()

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.F11:
            display.toggle_fullscreen()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.SPACE:
            # Space is a word break while there is a line to answer and
            # the way on at every other moment. There is no third key
            # for it because a sentence has spaces in it.
            if self.phase == 'reading':
                self.space()
            else:
                self.advance()
            return pyglet.event.EVENT_HANDLED
        # Every letter is a move here, C included, so the options key
        # is O alone rather than the C the rest of the workshop uses.
        if symbol == key.O and self.phase != 'reading':
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        if symbol in (key.ENTER, key.RETURN, key.NUM_ENTER):
            self.submit()
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.erase()
        elif key.A <= symbol <= key.Z:
            self.write(LETTERS[symbol - key.A])
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        """Start a run, or go on to the next line. That is the whole mouse.

        A line of text is not a place, so there is nothing here to
        point at. See the module docstring: the affordances that
        suggested themselves were all a second game.
        """
        self.advance()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
