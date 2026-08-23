# -*- coding: utf-8 -*-
"""The syllogism screen: lines on the wall, and what follows from them.

The reasoning lives in :mod:`neural_workshop.syllogism`; this module
is the page drawn and the keys that answer it. Four decisions matter:

* **Every answer the family has is on the screen, always.** Not a
  shortlist, and not a set that shrinks on the easy rungs. An option
  that is never right at a rung is a free elimination, and a list
  that changes length says something about the question before it is
  read. The direction families are the exception that proves it: they
  never leave a question open, so they do not offer *cannot be told*
  at all rather than offering it and never meaning it.

* **The convention is printed, because it is a choice.** Nothing is
  equal to anything else in an order, so *not more than* means *less
  than*; a step on the grid is one square; and *every X is a Y* does
  not say there are any X. A player who has to guess which of those
  the task meant is being tested on the task rather than on the
  premises.

* **A wrong answer is shown the working** — the lines that mattered,
  in the order they compose, and the conclusion. On a *nothing
  follows* it is shown two worlds instead: both satisfy every
  premise and they disagree, which is what nothing following means.

* **Picking is by index, and the pointer is only for people.** The
  agent boundary calls :meth:`choose` with the number it means. A
  keyboard gets arrows and Enter, and the first nine get their own
  keys, because twenty-seven directions is more than a numbered list
  can carry.

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
from ..syllogism import (BINARY, CATEGORICAL, GRADES, META, ORDER, PARITY,
                         PLANE, Question, SPACE, correct, generate, grade_of)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: The option the player is on, as against the ones they are not.
MINE = (0, 114, 178)           # blue

#: What each family takes for granted, said out loud. These are
#: choices rather than facts, and a task that left them unsaid would
#: be testing whether you guessed the same ones.
HINTS = {
    ORDER: _('no two of them are equal, so "not more than" means "less '
             'than"'),
    PARITY: _('there are two ways to be and no third'),
    PLANE: _('one square at a time; "north and east" means north of it '
             'and east of it'),
    SPACE: _('one square at a time, in three directions'),
    CATEGORICAL: _('"every X is a Y" does not say there are any X'),
    META: _('the same kind means the same relation, not the same things'),
    BINARY: _('a claim can be true, false, or not settled by the lines'),
}


#: Twenty-seven answers do not fit across a page written out in
#: full, so the widest family shortens them — for the eye only. The
#: option a player picks is still the sentence the working uses.
SHORTER = {'north': 'N', 'south': 'S', 'east': 'E', 'west': 'W',
           'above': 'up', 'below': 'down'}


def spread(count: int) -> int:
    """How many columns that many answers want."""
    if count <= 5:
        return 1
    return 3 if count <= 12 else 4


def shorten(text: str, count: int) -> str:
    """An answer as it is drawn, which is not always as it is meant."""
    if count <= 12:
        return text
    return ' '.join(SHORTER.get(word, word) for word in text.split()
                    if word != 'and')


class Syllogism:
    """Read the lines, work out what follows, pick it."""

    instance: Optional['Syllogism'] = None

    def __init__(self) -> None:
        if Syllogism.instance is not None:
            Syllogism.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.question: Optional[Question] = None
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
        Syllogism.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SYLLOGISM)
        self.start_rung = int(opts['SYLLOGISM_LEVEL'])
        self.total_trials = int(opts['SYLLOGISM_TRIALS'])
        self.show_working = bool(opts['SYLLOGISM_SHOW_WORKING'])
        self.adaptive = bool(opts['SYLLOGISM_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('syllogism', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _floor(self) -> float:
        """Nothing this task draws goes below here.

        The option a player is on is drawn in blue, and blue on a pale
        page has a rim of every blend between the two, part of which
        the band reader counts as a verdict. So the guard is the
        geometry rather than the palette, and the tests assert it at
        three window sizes rather than trusting a sweep to notice.
        """
        return above_the_band(from_bottom_edge(52))

    def _top(self) -> float:
        """Where the premises start. Everything below flows from them.

        Fixed fractions of the page were tried first and they do not
        work here: a rung prints two lines and another prints
        thirteen, and a block anchored at its middle grows both ways
        into whatever is above and below it. So each piece is
        measured after its text is set and the next one starts under
        it.
        """
        return from_top_edge(108)

    def _premise_size(self) -> float:
        many = len(self.question.lines) if self.question else 4
        return calc_fontsize(15 if many <= 6 else 13 if many <= 10 else 11)

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        wide = state.window.width * 0.88
        self.title = pyglet.text.Label(
            _('Syllogisms'), font_size=calc_fontsize(22), weight='bold',
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
        self.premises = pyglet.text.Label(
            '', font_size=self._premise_size(), color=self.textcolor,
            batch=self.batch, x=width_center(), y=self._top(),
            anchor_x='center', anchor_y='top', font_name=FONTLIST,
            multiline=True, width=wide, align='center')
        self.asked = pyglet.text.Label(
            '', font_size=calc_fontsize(16), weight='bold',
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
        """One label an answer, in as many columns as they need."""
        self.options = []
        if self.question is None:
            return
        offered = self.question.options
        size = self._option_size(spread(len(offered)))
        for number, text in enumerate(offered):
            shown = shorten(text, len(offered))
            if len(offered) <= 9:
                shown = '%d. %s' % (number + 1, shown)
            self.options.append(pyglet.text.Label(
                shown, font_size=size, color=self.textcolor,
                batch=self.batch, x=width_center(), y=0,
                anchor_x='center', anchor_y='center', font_name=FONTLIST))

    def _place_options(self, top: float) -> None:
        """Down the page from *top*, and never into the band.

        The step is whatever fits rather than whatever looks right,
        and the writing shrinks with it. A rung can print thirteen
        premises above twenty-seven answers, and a step chosen without
        looking would put the last row in the band on a small window —
        which a sweep would catch only sometimes, because how far down
        the rows reach depends on what was dealt. So the guard is the
        arithmetic here rather than the sweep.
        """
        if not self.options:
            return
        columns = spread(len(self.options))
        rows = (len(self.options) + columns - 1) // columns
        bottom = self._floor() + 10
        top = max(top, bottom)
        step = min(calc_fontsize(30), (top - bottom) / rows)
        wide = state.window.width * 0.92 / columns
        size = min(self._option_size(columns), max(6.0, step * 0.62))
        for number, label in enumerate(self.options):
            column, row = number // rows, number % rows
            label.font_size = size
            label.x = int(width_center()
                          + (column - (columns - 1) / 2.0) * wide)
            label.y = top - (row + 0.5) * step

    @staticmethod
    def _option_size(columns: int) -> float:
        return calc_fontsize(14 if columns == 1 else 12 if columns == 3
                             else 11)

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.question = None
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
            # A rung that could not build a question that reads back
            # off its own page. Said rather than retried forever, and
            # rather than dealt unchecked.
            self.phase = 'done'
            self.message = _('No question could be built at this level')
            self._redraw()
            return
        self.question = made
        self.choice = 0
        self.answered = None
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'asking'
        self.message = _(grade_of(self.rung).name)
        self._build_chrome()

    # --- playing ---------------------------------------------------------

    def move(self, step: int) -> None:
        """Walk the highlight. For people; the boundary picks outright."""
        if self.phase != 'asking' or self.question is None:
            return
        count = len(self.question.options)
        self.choice = (self.choice + step) % count
        self._redraw()

    def submit(self) -> None:
        """Answer with whatever is highlighted."""
        if self.phase == 'asking':
            self.choose(self.choice)

    def choose(self, number: int) -> None:
        """Answer with option *number*. Out of range does nothing."""
        if self.phase != 'asking' or self.question is None:
            return
        if not 0 <= int(number) < len(self.question.options):
            return
        self.choice = int(number)
        self._judge()

    def _judge(self) -> None:
        took = self.clock() - self.started_at
        right = correct(self.question, self.choice)
        self.answered = self.choice
        self.results.append((self.rung, right, took))
        self.message = (_('Right') if right
                        else _('No — it was "%s"') % self.question.shown_answer)
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
        if self.question is not None and self.phase in ('asking', 'judged'):
            if self.phase == 'asking':
                self.premises.text = '\n'.join(self.question.lines)
                self.note.text = HINTS.get(self.question.grade.family, '')
            else:
                self.premises.text = ('\n'.join(self.question.working)
                                      if self.show_working
                                      else '\n'.join(self.question.lines))
                self.note.text = ''
            self.asked.text = self.question.asked
        else:
            self.premises.text = ''
            self.asked.text = ''
            self.note.text = ''
        self._lay_out()
        self._colour_options()
        self._update_status()

    def _lay_out(self) -> None:
        """Each block under the one before it, measured rather than guessed."""
        gap = calc_fontsize(16)
        self.premises.y = self._top()
        self.asked.y = (self._top() - self.premises.content_height - gap
                        if self.premises.text else self._top())
        under = self.asked.y - gap
        if self.asked.text:
            under -= self.asked.content_height
        self._place_options(under)

    def _colour_options(self) -> None:
        """Blue for the one being pointed at, and for the one given."""
        for number, label in enumerate(self.options):
            if self.phase == 'ready' or self.question is None:
                label.color = self.textcolor
                continue
            picked = (self.answered if self.phase != 'asking'
                      else self.choice)
            label.color = (MINE + (255,) if number == picked
                           else self.textcolor)

    def _update_status(self) -> None:
        parts = [self.message]
        if self.question is not None and self.phase == 'asking':
            parts.append(_('question %d/%d') % (self.trial, self.total_trials))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Syllogism.instance is not self:
            return
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        Syllogism.instance = None

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
