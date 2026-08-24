# -*- coding: utf-8 -*-
"""The Overrun screen: one line of text, one margin, and a keyboard.

The arithmetic lives in :mod:`neural_workshop.overrun` and the text in
:mod:`neural_workshop.sentences`; this module is the lane drawn and the
keys that empty it. Four decisions matter here.

* **The line is drawn on a character grid, one label a letter.** It
  looks like a terminal and that is a side effect — the reason is that
  the rules module decides when a line has run out by counting
  characters, and a proportional font would make that a different
  question from the one the eye is asking. On the grid the two are the
  same question: the cell the arithmetic kills the line in is the cell
  the glyph is standing in. ``tests/test_overrun.py`` asserts every
  glyph fits inside its own cell, so the line is never taken away while
  it still looks clear of the margin.

* **The word being typed is always at the left-hand end.** Clearing one
  takes the front off the line and everything behind it moves up, so
  the place to look moves only with the clock and never with the
  typing. It is also what makes the game a tug of war rather than a
  chase: the drift pushes the end of the line at the margin and every
  word typed hauls it back by its own width.

* **A wrong letter stays where it was put.** It is drawn in vermillion
  over the letter it should have been, and the word will not clear
  until it is rubbed out. Ignoring a wrong key was kinder and it is not
  what a keyboard does; the cost of ignoring it is in the module
  docstring next door, and it is the whole floor of the task.

* **Nothing here is a place to point at.** Like Scramble, the pointer
  starts a run and goes on to the next wave, and that is the whole of
  the mouse. There is no word to click: the line decides what you type
  next, not you.

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
from ..overrun import (CELLS, GRADES, MOST_LIVES, START_LIVES, Wave,
                       generate, grade_of, overrun, words_a_minute)
from ..sentences import have, missing_message
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

LETTERS = 'abcdefghijklmnopqrstuvwxyz'

#: A letter that landed where it belongs, and one that did not.
RIGHT = (0, 114, 178)          # blue
WRONG = (213, 94, 0)           # vermillion
#: The margin the line must not reach, and the track it runs along.
MARGIN = (204, 121, 167)       # reddish purple
TRACK = (128, 128, 128)

#: How long the verdict stays up before the next wave is dealt. On the
#: task's own clock, which under an agent boundary is the driver's.
SETTLE_SECONDS = 0.7


class Overrun:
    """Type the line away before its end reaches the margin."""

    instance: Optional['Overrun'] = None

    def __init__(self) -> None:
        if Overrun.instance is not None:
            Overrun.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.wave: Optional[Wave] = None
        self.cleared = 0
        self.typed = ''
        self.drift = 0.0
        self.lives = START_LIVES
        self.trial = 0
        self.until = 0.0
        self.started_at = 0.0
        self.landed = 0
        self.missed = 0
        self.seconds = 0.0
        self.results: List[Tuple[int, bool, int, float]] = []
        self.phase = 'ready'
        #: A verdict after every key, for a learner that would otherwise
        #: be paid once a wave. Off for people, and the boundary turns it
        #: off again for any build that will not pay per action.
        self.coach = False
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.message = _('Press Space to start')
        self.chars: List[object] = []
        self.owner: List[int] = []
        self.slot: List[int] = []
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        Overrun.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.OVERRUN)
        self.start_rung = int(opts['OVERRUN_LEVEL'])
        self.total_waves = int(opts['OVERRUN_WAVES'])
        self.adaptive = bool(opts['OVERRUN_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    @staticmethod
    def stocked() -> bool:
        """Whether the fetched text is there, as against the seed."""
        return have()

    def open_options(self) -> None:
        taskoptions.open_task_options('overrun', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _floor(self) -> float:
        """Nothing this task draws goes below here.

        The line is drawn in three saturated colours and the margin in a
        fourth, so the guard has to be the geometry rather than the
        palette: any of them has a blend with the page that the boundary
        would read as a verdict.
        """
        return above_the_band(from_bottom_edge(56))

    def _lane(self) -> Tuple[float, float, float, float]:
        """Left edge, margin, middle height, and the width of one cell."""
        left = state.window.width * 0.05
        right = state.window.width * 0.95
        bottom = self._floor()
        top = from_top_edge(126)
        middle = bottom + max(60.0, top - bottom) * 0.55
        return left, right, middle, (right - left) / CELLS

    def _cell_font(self, cell: float) -> float:
        """A font size whose widest lowercase letter fits inside a cell.

        Measured rather than guessed at, because the answer depends on
        whichever of :data:`~neural_workshop.constants.FONTLIST` this
        machine actually has, and a letter wider than its cell would put
        the drawing and the arithmetic into disagreement about where the
        end of the line is.
        """
        probe = pyglet.text.Label('m', font_size=24.0, font_name=FONTLIST)
        wide = probe.content_width
        probe.delete()
        if not wide:                                   # pragma: no cover
            return calc_fontsize(13)
        return 24.0 * cell * 0.90 / wide

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.chars = []
        self.title = pyglet.text.Label(
            _('Overrun'), font_size=calc_fontsize(22), weight='bold',
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
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   type the line'
              '   Backspace: rub out   O: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self._build_track()
        self._build_lives()
        # Read by the agent boundary, which pays a wave by this label's
        # colour; tests/check_band.py is what says nothing else this task
        # draws puts a saturated colour in the bottom quarter. Rebuilt
        # with the chrome, so a verdict already up is put back.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._build_line()
        self._redraw()

    def _build_track(self) -> None:
        """The road the line runs along, and the margin at the end of it."""
        left, right, middle, cell = self._lane()
        reach = min(cell * 3.0, (middle - self._floor()) * 0.8)
        self.drawn.append(pyglet.shapes.Line(
            left, middle - reach, right, middle - reach, thickness=2.0,
            color=TRACK, batch=self.batch))
        self.drawn.append(pyglet.shapes.Line(
            right, middle - reach, right, middle + reach, thickness=5.0,
            color=MARGIN, batch=self.batch))

    def _build_lives(self) -> None:
        """One disc a life, filled while it is held.

        Drawn rather than counted in words because it is the one number
        a player has to read while doing something else.
        """
        self.life_discs: List[object] = []
        radius = max(3.0, state.window.width * 0.006)
        step = radius * 3.0
        first = width_center() - step * (MOST_LIVES - 1) / 2.0
        for index in range(MOST_LIVES):
            self.life_discs.append(pyglet.shapes.Circle(
                first + index * step, from_top_edge(112), radius,
                color=self.textcolor[:3], batch=self.batch))

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.wave = None
        self.cleared = 0
        self.typed = ''
        self.drift = 0.0
        self.lives = START_LIVES
        self.landed = 0
        self.missed = 0
        self.seconds = 0.0
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.lives <= 0 or self.trial >= self.total_waves:
            self._finish()
            return
        made = generate(self.rung, seed=self.rng.randrange(1 << 30))
        if made is None:
            # No sentence short enough to run this lane. With the seed
            # text that is a real state and not a crash.
            self.phase = 'done'                        # pragma: no cover
            self.message = _('No sentence at this level')
            self._redraw()
            return
        self.trial += 1
        self.wave = made
        self.cleared = 0
        self.typed = ''
        self.drift = 0.0
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'typing'
        self.message = _(grade_of(self.rung).name)
        self._build_line()
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d of %d waves clear, %d words a minute, '
                         '%d lives left') % (
            tally['cleared'], tally['waves'], tally['wpm'], tally['lives'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        return {
            'waves': len(self.results),
            'cleared': sum(1 for _r, done, _l, _t in self.results if done),
            'lives': self.lives,
            'best_rung': max((rung for rung, done, _l, _t in self.results
                              if done), default=0),
            'wpm': int(round(words_a_minute(self.landed, self.seconds))),
            'missed': self.missed,
        }

    # --- playing ---------------------------------------------------------

    def _target(self) -> str:
        """The word at the front of the line, which is the one to type."""
        if self.wave is None or self.cleared >= len(self.wave.words):
            return ''
        return self.wave.words[self.cleared]

    def write(self, letter: str) -> None:
        """Put one letter into the word at the front of the line.

        Refused once the word's own width is full: a buffer that is
        wrong and full has nowhere to go but the rub-out, and letting it
        grow past the word would put the line's letters out of their
        cells.
        """
        if self.phase != 'typing' or letter not in LETTERS:
            return
        word = self._target()
        if not word or len(self.typed) >= len(word):
            self._paid_nothing()
            return
        landed = letter == word[len(self.typed)]
        self.typed += letter
        # Only the ones that landed, so the rate printed at the end of a
        # run is a net rate rather than a count of how hard the keyboard
        # was hit. A letter rubbed out and typed again counts twice,
        # which is the one way this is generous and is the same way
        # every typing test is.
        if landed:
            self.landed += 1
        else:
            self.missed += 1
        if self.typed == word:
            self.cleared += 1
            self.typed = ''
            if self.cleared >= len(self.wave.words):
                self._wave_clear()
                return
        self._paid(landed)
        self._redraw()

    def erase(self) -> None:
        """Take back the last letter. Pays nothing, by design.

        A rub-out that paid would be a rub-out worth doing on its own,
        and typing a wrong letter to earn the credit for rubbing it out
        is a loop that never ends.
        """
        if self.phase != 'typing' or not self.typed:
            self._paid_nothing()
            return
        self.typed = self.typed[:-1]
        self._paid_nothing()
        self._redraw()

    # --- what a key is worth ---------------------------------------------

    def _paid(self, landed: bool) -> None:
        """The wave's own outcome, taken apart one key at a time.

        Not shaping and it does not claim to be: there is no potential
        here and nothing telescopes. A letter that lands is a piece of
        the green a cleared wave would have been and a letter that
        misses is a piece of the red, which orders policies the way the
        wave's single verdict does. It diverges in the way Cookie
        Thief's does and it is worth writing down: the wave is
        all-or-nothing and this sum is graded, so a learner paid this
        way is paid for thirty-nine letters of a wave it lost.
        """
        if not self.coach:
            return
        self.verdict_shown = (landed, _('yes') if landed else _('no'))
        self.verdict.show(*self.verdict_shown)

    def _paid_nothing(self) -> None:
        """A key that changed nothing clears the label and pays zero."""
        if not self.coach:
            return
        self.verdict_shown = None
        self.verdict.clear()

    # --- the two ways a wave ends ----------------------------------------

    def _wave_clear(self) -> None:
        self.lives = min(MOST_LIVES, self.lives + 1)
        self._settle(True, _('Clear — a life back'))

    def _spoil(self) -> None:
        self.lives -= 1
        self._settle(False, _('The line ran out'))

    def _settle(self, cleared: bool, said: str) -> None:
        took = max(1e-6, self.clock() - self.started_at)
        self.seconds += took
        self.results.append((self.rung, cleared, self.cleared, took))
        if self.adaptive:
            self.rung = self.clamped(self.rung + (1 if cleared else -1))
        self.message = said
        self.verdict_shown = (cleared, said)
        self.verdict.show(*self.verdict_shown)
        self.phase = 'settled'
        self.until = self.clock() + SETTLE_SECONDS
        self._redraw()

    # --- the clock -------------------------------------------------------

    def update(self, dt: float) -> None:
        """Move the line, and deal the next wave once this one has settled."""
        if self.phase == 'typing' and self.wave is not None:
            # Clamped, so a stall on a slow machine does not teleport the
            # line past the margin without anyone having had a chance.
            self.drift += self.wave.grade.speed * min(dt, 0.1)
            if overrun(self.wave, self.cleared, self.drift):
                self._spoil()
            else:
                self._redraw()
        elif self.phase == 'settled' and self.clock() >= self.until:
            self._next_trial()

    # --- drawing ---------------------------------------------------------

    def _build_line(self) -> None:
        """One label a letter, laid out on the lane's character grid.

        Spaces get no label. They are still cells — the arithmetic
        counts them, and they are what a cleared word hands back along
        with its own letters — but there is nothing to draw in one.
        """
        for label in self.chars:
            label.delete()
        self.chars, self.owner, self.slot = [], [], []
        if self.wave is None:
            return
        _left, _right, middle, cell = self._lane()
        size = self._cell_font(cell)
        for index, word in enumerate(self.wave.words):
            at = self.wave.starts[index]
            for step, letter in enumerate(word):
                self.chars.append(pyglet.text.Label(
                    letter, font_size=size, color=self.textcolor,
                    batch=self.batch, x=0, y=middle, anchor_x='center',
                    anchor_y='center', font_name=FONTLIST))
                self.owner.append(index)
                self.slot.append(at + step)

    def _redraw(self) -> None:
        self._place_line()
        self._show_lives()
        self._update_status()

    def _place_line(self) -> None:
        if self.wave is None or self.phase in ('ready', 'done'):
            for label in self.chars:
                label.text = ''
            return
        left, _right, _middle, cell = self._lane()
        wave = self.wave
        # What the cleared words took away with them. The line is drawn
        # from the original offsets less this, which is what makes the
        # remaining words snap left by the width of the one that went.
        gone = (wave.starts[self.cleared] if self.cleared < len(wave.words)
                else wave.length)
        origin = left + (wave.start_cell + self.drift - gone) * cell
        word = self._target()
        for index, label in enumerate(self.chars):
            owns = self.owner[index]
            if owns < self.cleared:
                label.text = ''
                continue
            label.x = origin + (self.slot[index] + 0.5) * cell
            step = self.slot[index] - wave.starts[owns]
            if owns == self.cleared and step < len(self.typed):
                label.text = self.typed[step]
                label.color = ((RIGHT if self.typed[step] == word[step]
                                else WRONG) + (255,))
            else:
                label.text = wave.words[owns][step]
                label.color = self.textcolor

    def _show_lives(self) -> None:
        for index, disc in enumerate(self.life_discs):
            disc.visible = index < max(0, self.lives)

    def _update_status(self) -> None:
        parts = [self.message]
        if self.wave is not None and self.phase in ('typing', 'settled'):
            parts.append(_('wave %d/%d   %d words a minute   %d lives')
                         % (self.trial, self.total_waves,
                            int(round(words_a_minute(self.wave.letters,
                                                     self.wave.seconds))),
                            max(0, self.lives)))
        if self.phase == 'ready' and not self.stocked():
            parts.append(missing_message())
        self.status.text = '     '.join(parts)
        self.note.text = (_('Type the line away before its end reaches the '
                            'margin.') if self.phase == 'ready' else '')

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Overrun.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        Overrun.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events ----------------------------------------------------------

    def advance(self) -> None:
        """Whatever Space or a click means in the phase we are in."""
        if self.phase in ('ready', 'done'):
            self.start_run()

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.F11:
            display.toggle_fullscreen()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.SPACE:
            # A space is not a key in this game — the words clear
            # themselves and the gaps are handed back with them — so it
            # is free to be the way on.
            self.advance()
            return pyglet.event.EVENT_HANDLED
        # Every letter is a move here, C included, so the options key is
        # O alone rather than the C the rest of the workshop uses.
        if symbol == key.O and self.phase != 'typing':
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        if symbol in (key.BACKSPACE, key.DELETE):
            self.erase()
        elif key.A <= symbol <= key.Z:
            self.write(LETTERS[symbol - key.A])
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        """Start a run. That is the whole of the mouse.

        There is nothing here to point at: the line decides which word
        comes next, so clicking one could only ever mean what typing it
        already means.
        """
        self.advance()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
