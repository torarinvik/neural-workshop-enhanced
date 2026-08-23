# -*- coding: utf-8 -*-
"""The trivia screen: one question, and the answers it is not.

The questions and the wrong answers live in :mod:`neural_workshop.trivia`;
this module is the page drawn and the keys that answer it. Four
decisions matter, and three of them are the same ones the syllogism
screen made for the same reasons:

* **Picking is by index, and the pointer is only for people.** The
  agent boundary calls :meth:`choose` with the number it means. A
  keyboard gets arrows and Enter, and every option gets its own digit,
  because eight is a list a person can count.

* **The options are drawn in one column.** An answer here can be
  *the International Court of Justice*, and a three-column layout
  either wraps it or shrinks the whole page to the width of its
  longest row. Eight rows of one column fit.

* **A wrong answer is shown the right one**, because a trivia question
  a player got wrong and is not told the answer to has taught nobody
  anything. This is the only kind of working there is here: the
  dataset gives an answer, not a derivation.

* **The pool is named on the screen.** With nothing fetched the game
  deals from the hundred-odd questions written into
  :data:`neural_workshop.trivia.SEED`, and a player who has seen them
  should be told they are seeing them again rather than left to
  wonder. The line is on the options screen and in the status while a
  run is idle, and it is not printed while a question is up — a
  distraction on the frame the trial is answered on is a distraction
  in the data.

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
from ..trivia import (GRADES, Round, bank, correct, fetched, generate,
                      grade_at, missing_message)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: The option the player is on, as against the ones they are not.
MINE = (0, 114, 178)           # blue

#: And the one that was right, once it no longer matters.
RIGHT = (0, 158, 115)          # bluish green


class Trivia:
    """Read the question, pick the answer."""

    instance: Optional['Trivia'] = None

    def __init__(self) -> None:
        if Trivia.instance is not None:
            Trivia.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.round: Optional[Round] = None
        self.choice = 0
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, bool, float]] = []   # rung, right, secs
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.answered: Optional[int] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.message = _('Press Space to start')
        self.options: List[pyglet.text.Label] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Trivia.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.TRIVIA)
        self.start_rung = int(opts['TRIVIA_LEVEL'])
        self.total_trials = int(opts['TRIVIA_TRIALS'])
        self.show_answer = bool(opts['TRIVIA_SHOW_ANSWER'])
        self.adaptive = bool(opts['TRIVIA_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('trivia', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _floor(self) -> float:
        """Nothing this task draws goes below here.

        The option a player is on is drawn in blue and the right one in
        green, and either on a pale page has a rim of every blend
        between the two, part of which the band reader counts as a
        verdict. So the guard is the geometry rather than the palette,
        and the tests assert it at three window sizes rather than
        trusting a sweep to notice.
        """
        return above_the_band(from_bottom_edge(52))

    def _top(self) -> float:
        """Where the question starts. Everything below flows from it."""
        return from_top_edge(108)

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        wide = state.window.width * 0.88
        self.title = pyglet.text.Label(
            _('Trivia'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(64),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.note = pyglet.text.Label(
            '', font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(88),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.asked = pyglet.text.Label(
            '', font_size=calc_fontsize(17), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=self._top(), anchor_x='center',
            anchor_y='top', font_name=FONTLIST, multiline=True,
            width=wide, align='center')
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   arrows: choose'
              '   Enter: answer   O: options'),
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
        self._build_options()
        self._redraw()

    def _build_options(self) -> None:
        """One label an answer, numbered, down the page."""
        self.options = []
        if self.round is None:
            return
        for number, text in enumerate(self.round.options):
            self.options.append(pyglet.text.Label(
                '%d. %s' % (number + 1, text), font_size=calc_fontsize(14),
                color=self.textcolor, batch=self.batch,
                x=width_center(), y=0, anchor_x='center',
                anchor_y='center', font_name=FONTLIST))

    def _place_options(self, top: float) -> None:
        """Down the page from *top*, and never into the band.

        The step is whatever fits rather than whatever looks right, and
        the writing shrinks with it. A rung prints two options and
        another prints eight under a question that is itself three
        lines long, and a step chosen without looking would put the
        last row in the band on a small window — which a sweep would
        catch only sometimes, because how far down the rows reach
        depends on what was dealt.
        """
        if not self.options:
            return
        bottom = self._floor() + 10
        top = max(top, bottom)
        step = min(calc_fontsize(34), (top - bottom) / len(self.options))
        size = min(calc_fontsize(14), max(6.0, step * 0.55))
        for number, label in enumerate(self.options):
            label.font_size = size
            label.x = int(width_center())
            label.y = top - (number + 0.5) * step

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.round = None
        self.choice = 0
        self.answered = None
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
            # An empty pool, which is a thing said rather than dealt
            # around. There is no retrying past it: the questions are
            # a file, and either it is there or it is not.
            self.phase = 'done'
            self.message = _('No questions to ask')
            self._redraw()
            return
        self.round = made
        self.choice = 0
        self.answered = None
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'asking'
        self.message = _(grade_at(self.rung).name)
        self._build_chrome()

    # --- playing ---------------------------------------------------------

    def move(self, step: int) -> None:
        """Walk the highlight. For people; the boundary picks outright."""
        if self.phase != 'asking' or self.round is None:
            return
        self.choice = (self.choice + step) % len(self.round.options)
        self._redraw()

    def submit(self) -> None:
        """Answer with whatever is highlighted."""
        if self.phase == 'asking':
            self.choose(self.choice)

    def choose(self, number: int) -> None:
        """Answer with option *number*. Out of range does nothing."""
        if self.phase != 'asking' or self.round is None:
            return
        if not 0 <= int(number) < len(self.round.options):
            return
        self.choice = int(number)
        self._judge()

    def _judge(self) -> None:
        took = self.clock() - self.started_at
        right = correct(self.round, self.choice)
        self.answered = self.choice
        self.results.append((self.rung, right, took))
        self.message = (_('Right') if right
                        else _('No — it was "%s"') % self.round.shown_answer)
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
        if self.round is not None and self.phase in ('asking', 'judged'):
            self.asked.text = self.round.asked
            self.note.text = ''
        else:
            self.asked.text = ''
            self.note.text = '' if fetched() else missing_message()
        self._lay_out()
        self._colour_options()
        self._update_status()

    def _lay_out(self) -> None:
        """The options under the question, measured rather than guessed."""
        gap = calc_fontsize(20)
        self.asked.y = self._top()
        under = self._top() - gap
        if self.asked.text:
            under -= self.asked.content_height
        self._place_options(under)

    def _colour_options(self) -> None:
        """Blue for the one being pointed at, and green for the right one
        once the answer is in."""
        for number, label in enumerate(self.options):
            if self.phase == 'ready' or self.round is None:
                label.color = self.textcolor
                continue
            if self.phase == 'asking':
                label.color = (MINE + (255,) if number == self.choice
                               else self.textcolor)
                continue
            if self.show_answer and number == self.round.answer:
                label.color = RIGHT + (255,)
            elif number == self.answered:
                label.color = MINE + (255,)
            else:
                label.color = self.textcolor

    def _update_status(self) -> None:
        parts = [self.message]
        if self.round is not None and self.phase == 'asking':
            parts.append(_('question %d/%d') % (self.trial, self.total_trials))
        elif self.phase in ('ready', 'done'):
            parts.append(_('%d questions in the pool') % len(bank()))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Trivia.instance is not self:
            return
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        Trivia.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='long_term_memory')

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
        if symbol == key.O and self.phase != 'asking':
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.SPACE and self.phase != 'asking':
            self.advance()
            return pyglet.event.EVENT_HANDLED
        if self.phase == 'asking':
            if symbol in (key.DOWN, key.RIGHT):
                self.move(1)
            elif symbol in (key.UP, key.LEFT):
                self.move(-1)
            elif symbol in (key.ENTER, key.RETURN, key.NUM_ENTER, key.SPACE):
                self.submit()
            elif key._1 <= symbol <= key._9:
                self.choose(symbol - key._1)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        """Start a run, or go on. Answering is by key, not by aim."""
        if self.phase != 'asking':
            self.advance()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
