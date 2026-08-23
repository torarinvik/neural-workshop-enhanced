# -*- coding: utf-8 -*-
"""The algebra screen: a question above, what you make of it below.

The reasoning lives in :mod:`neural_workshop.algebra` and the exact
arithmetic in :mod:`neural_workshop.expressions`; this module is the
question drawn and the keys that answer it. Four decisions matter:

* **One free line, whatever the rung wants.** Low rungs want a
  number, high ones want a polynomial, and both are typed into the
  same line and marked by the same parser. Boxes sized to the answer
  would say how many terms it has, which on a collecting rung is most
  of the work.

* **Characters come from ``on_text``, not from key codes.** ``+`` is
  shift-equals on one keyboard and its own key on another, and a task
  that mapped key codes would be about the keyboard. The agent
  boundary does not go through either — it calls :meth:`write` with
  the character it means.

* **How big the search is, is printed.** It is measured rather than
  guessed and it gives nothing away: it is a count of what is *not*
  determined. At the bottom it says the answer is one of about twenty.
  At the top it says one of about 10^28, which is the honest
  description of a rung nothing will ever search.

* **A wrong answer is shown the working.** Not just the answer — the
  derivation, line by line. Told only that they were wrong about a
  congruence, a player has learned nothing; shown that seven has
  inverse fifteen mod twenty-six, they have learned the rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..algebra import GRADES, Problem, correct, generate, grade_of
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: What the player has typed, as against the question above it.
MINE = (0, 114, 178)           # blue

#: Everything a player may type into an answer. Anything else is
#: ignored rather than refused loudly — a stray key is a slip.
ALLOWED = '0123456789xy+-*/^() '


def search_line(problem: Problem) -> str:
    """How many values the rung leaves standing before any reasoning."""
    size = problem.candidates
    if size < 1.5:
        return _('the answer is one of about %d') % round(10 ** size)
    if size < 5:
        return _('the answer is one of about %s') % '{:,}'.format(
            int(round(10 ** size)))
    return _('the answer is one of about 10^%d') % round(size)


class Algebra:
    """Work it out and type it in. Enter checks it."""

    instance: Optional['Algebra'] = None

    def __init__(self) -> None:
        if Algebra.instance is not None:
            Algebra.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.problem: Optional[Problem] = None
        self.typed = ''
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, bool, float]] = []   # rung, right, secs
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_text,
                                   self.on_mouse_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Algebra.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.ALGEBRA)
        self.start_rung = int(opts['ALGEBRA_LEVEL'])
        self.total_trials = int(opts['ALGEBRA_TRIALS'])
        self.show_working = bool(opts['ALGEBRA_SHOW_WORKING'])
        self.adaptive = bool(opts['ALGEBRA_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('algebra', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _floor(self) -> float:
        """Nothing this task draws goes below here.

        The typed line is blue, and blue on a pale page has a rim of
        every blend between the two, part of which the band reader
        counts as a verdict. So the guard is the geometry rather than
        the palette, and the tests assert it at three window sizes
        rather than trusting a sweep to notice.
        """
        return above_the_band(from_bottom_edge(52))

    def _lines(self) -> Tuple[float, float, float]:
        """Where the question, the working and the answer sit."""
        top = from_top_edge(116)
        bottom = self._floor()
        height = max(60.0, top - bottom)
        return (bottom + height * 0.74, bottom + height * 0.46,
                bottom + height * 0.16)

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        wide = state.window.width * 0.88
        asked, working, answer = self._lines()
        self.title = pyglet.text.Label(
            _('Algebra'), font_size=calc_fontsize(22), weight='bold',
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
        self.question = pyglet.text.Label(
            '', font_size=calc_fontsize(20), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=asked, anchor_x='center',
            anchor_y='center', font_name=FONTLIST, multiline=True,
            width=wide, align='center')
        self.working = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=self.textcolor,
            batch=self.batch, x=width_center(), y=working,
            anchor_x='center', anchor_y='center', font_name=FONTLIST,
            multiline=True, width=wide, align='center')
        self.entry = pyglet.text.Label(
            '', font_size=calc_fontsize(18), color=MINE + (255,),
            batch=self.batch, x=width_center(), y=answer,
            anchor_x='center', anchor_y='center', font_name=FONTLIST,
            multiline=True, width=wide, align='center')
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   type the answer'
              '   Enter: check   O: options'),
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
        self.problem = None
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
            # A rung that could not build a problem inside its own
            # guarantees. Said rather than retried forever, and rather
            # than dealt outside them.
            self.phase = 'done'
            self.message = _('No problem could be built at this level')
            self._redraw()
            return
        self.problem = made
        self.typed = ''
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'working'
        self.message = _(grade_of(self.rung).name)
        self._redraw()

    # --- playing ---------------------------------------------------------

    def write(self, character: str) -> None:
        """Add one character to the answer, if it is one we take."""
        if self.phase != 'working' or character not in ALLOWED:
            return
        if character == ' ' and (not self.typed or self.typed.endswith(' ')):
            return
        self.typed += character
        self._redraw()

    def erase(self) -> None:
        if self.phase != 'working' or not self.typed:
            return
        self.typed = self.typed[:-1]
        self._redraw()

    def submit(self) -> None:
        """Mark the answer. Refused while it is empty."""
        if self.phase != 'working' or not self.typed.strip():
            return
        self._judge()

    def _judge(self) -> None:
        took = self.clock() - self.started_at
        right = correct(self.problem, self.typed)
        self.results.append((self.rung, right, took))
        self.message = (_('Right') if right
                        else _('No — it was %s') % self.problem.shown_answer)
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
        asked, working, answer = self._lines()
        self.question.y, self.working.y, self.entry.y = asked, working, answer
        if self.problem is not None and self.phase in ('working', 'judged'):
            self.question.text = self.problem.asked
            if self.phase == 'working':
                self.note.text = search_line(self.problem)
                self.working.text = self.problem.wants
            else:
                self.note.text = ''
                self.working.text = ('\n'.join(self.problem.working)
                                     if self.show_working else '')
        else:
            self.question.text = ''
            self.note.text = ''
            self.working.text = ''
        if self.phase == 'working':
            self.entry.text = self.typed + '_'
        elif self.phase == 'judged':
            self.entry.text = self.typed
        else:
            self.entry.text = ''
        self._update_status()

    def _update_status(self) -> None:
        parts = [self.message]
        if self.problem is not None and self.phase == 'working':
            parts.append(_('question %d/%d') % (self.trial, self.total_trials))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Algebra.instance is not self:
            return
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_text,
                                     self.on_mouse_press, self.on_draw)
        Algebra.instance = None

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
        if symbol == key.SPACE and self.phase != 'working':
            self.advance()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.O and self.phase != 'working':
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        if symbol in (key.ENTER, key.RETURN, key.NUM_ENTER):
            self.submit()
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.erase()
        return pyglet.event.EVENT_HANDLED

    def on_text(self, text: str) -> bool:
        """Characters, from whatever key made them.

        A plus sign is shift-equals here and its own key there, and a
        task that read key codes would be teaching a keyboard.
        """
        for character in text:
            self.write(character.lower())
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        """Start a run, or go on. A question is not a place to point at."""
        self.advance()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
