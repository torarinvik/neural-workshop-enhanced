# -*- coding: utf-8 -*-
"""The crossword screen: arrows move, letters write, Tab turns the cursor.

The reasoning lives in :mod:`neural_workshop.crossword` and the words
in :mod:`neural_workshop.wordlist`; this module is the grid drawn, the
clue read out, and the keys that fill it. Four decisions matter here:

* **One clue at a time, not a list down the side.** A printed crossword
  shows every clue at once and a screen this size cannot. So the clue
  shown is the one for the entry the cursor is in, in the direction the
  cursor is facing, and Tab turns the cursor rather than moving it. The
  cost is that the grid can no longer be scanned for a clue you might
  know; the gain is that a clue is always legible, and the ladder is
  about crossings rather than about reading.

* **The mouse does what the mouse does in every crossword.** Click a
  cell to go to it; click the cell you are already on to turn between
  across and down. That second one is the convention every crossword
  on a screen has used for thirty years, and a task that invented its
  own would be teaching its own controls rather than testing anything.
  The letters stay on the keyboard, because they are letters.

* **A withheld clue says so.** At the top of the ladder some entries
  have no clue at all and must come from their crossings. The screen
  prints a dash rather than nothing, because an empty line reads as a
  bug and a dash reads as a rule.

* **A wrong letter is marked only if you ask.** With mistakes shown, a
  letter that contradicts the answer is marked the moment it is
  written, which turns the hard rungs into something a person can
  finish. Turned off, nothing is checked until the grid is full. It is
  one option and it changes the task, so the options note says so.

* **This task needs the definitions.** The seed word list carries no
  clues, so with nothing fetched the screen says what to run instead of
  dealing a puzzle without them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Set, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, state
from ..constants import FONTLIST
from ..crossword import GRADES, Puzzle, Slot, generate, grade_of
from ..geometry import (MAX_FONT_SIZE, calc_fontsize, from_bottom_edge,
                        from_top_edge, width_center)
from ..wordlist import index_ready, missing_message, pool, CLUES
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band
from ..i18n import _

#: The lines between cells.
RULE = (120, 120, 120)
#: The cell the cursor is on, and the rest of its entry.
HERE = (86, 180, 233)          # sky blue
LIT = (86, 180, 233, 50)
#: The cell under the pointer, which is not where the cursor is.
NEAR = (86, 180, 233, 22)
#: A letter that contradicts the answer, when mistakes are shown.
WRONG = (213, 94, 0)           # vermilion
#: What the player wrote, as against what came with the puzzle.
MINE = (0, 114, 178)           # blue

LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def fit(step: float, share: float) -> float:
    """A font size taken from the cell rather than from the window."""
    return max(5.0, min(MAX_FONT_SIZE, step * share))


class Crossword:
    """Fill the grid. Arrows move, letters write, Tab turns, Esc leaves."""

    instance: Optional['Crossword'] = None

    def __init__(self) -> None:
        if Crossword.instance is not None:
            Crossword.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.puzzle: Optional[Puzzle] = None
        self.filled: List[str] = []
        self.at = 0
        self.down = False
        #: The cell the pointer is over, for a hint of a highlight. Kept
        #: separate from :attr:`at` because hovering is not choosing.
        self.hovered: Optional[int] = None
        self.mistakes = 0
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, int, float]] = []   # rung, slips, secs
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.message = (_('Press Space to start') if self.stocked()
                        else missing_message(CLUES))
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_mouse_motion, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Crossword.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.CROSSWORD)
        self.start_rung = int(opts['CROSSWORD_LEVEL'])
        self.total_trials = int(opts['CROSSWORD_TRIALS'])
        self.show_mistakes = bool(opts['CROSSWORD_SHOW_MISTAKES'])
        self.adaptive = bool(opts['CROSSWORD_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    @staticmethod
    def stocked() -> bool:
        """Whether there are clues to set a puzzle from."""
        return index_ready() and pool().clued

    def open_options(self) -> None:
        taskoptions.open_task_options('crossword', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.ink = (fg, fg, fg)
        self.block = (fg, fg, fg)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Crossword'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(64),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.cluetext = pyglet.text.Label(
            '', font_size=calc_fontsize(15), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(92),
            anchor_x='center', anchor_y='center', font_name=FONTLIST,
            multiline=True, width=state.window.width * 0.9, align='center')
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   click or arrows: move'
              '   letters: write   Tab: turn   O: options'),
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

    def size(self) -> int:
        return self.puzzle.size if self.puzzle is not None else 1

    def _board(self) -> Tuple[float, float, float]:
        """Left, bottom and side of the whole grid on screen."""
        window = state.window
        top = from_top_edge(112)
        bottom = above_the_band(from_bottom_edge(44))
        side = max(40.0, min(window.width * 0.82, top - bottom))
        return ((window.width - side) / 2, bottom + (top - bottom - side) / 2,
                side)

    def _cell_rect(self, cell: int) -> Tuple[float, float, float]:
        left, bottom, side = self._board()
        step = side / self.size()
        x, y = cell % self.size(), cell // self.size()
        return (left + x * step, bottom + (self.size() - 1 - y) * step, step)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.puzzle = None
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = (_('Press Space to start') if self.stocked()
                        else missing_message(CLUES))
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        if not self.stocked():
            return
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        made = generate(self.rung, seed=self.rng.randrange(1 << 30))
        if made is None:
            # A rung whose budget ran out. Said rather than retried
            # forever: a grid this pool cannot fill is a fact about the
            # pool, and the next seed is unlikely to change it.
            self.phase = 'done'
            self.message = _('No grid could be built at this level')
            self._redraw()
            return
        self.puzzle = made
        self.filled = [made.solution[cell] if cell in made.givens else ''
                       for cell in range(made.size * made.size)]
        self.at = next((cell for cell in range(made.size * made.size)
                        if made.solution[cell] and not self.filled[cell]), 0)
        self.down = False
        self.hovered = None
        self.mistakes = 0
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'solving'
        grade = grade_of(self.rung)
        self.message = _('%s — %d to fill') % (_(grade.name), made.blanks())
        self._redraw()

    # --- what the cursor is in -------------------------------------------

    def slot_here(self) -> Optional[Slot]:
        """The entry the cursor is in, facing the way it faces."""
        if self.puzzle is None:
            return None
        for slot in self.puzzle.slots:
            if slot.down == self.down and self.at in slot.cells:
                return slot
        for slot in self.puzzle.slots:
            if self.at in slot.cells:
                return slot
        return None

    def clue_line(self) -> str:
        slot = self.slot_here()
        if slot is None:
            return ''
        where = _('%d down') % slot.number if slot.down \
            else _('%d across') % slot.number
        said = slot.clue or _('— no clue; get it from the crossings —')
        return '%s (%d):  %s' % (where, slot.length, said)

    # --- playing ---------------------------------------------------------

    def blocked(self, cell: int) -> bool:
        return self.puzzle is None or not self.puzzle.solution[cell]

    def given(self, cell: int) -> bool:
        return self.puzzle is not None and cell in self.puzzle.givens

    def move(self, dx: int, dy: int) -> None:
        """Step the cursor, skipping over blocks."""
        if self.phase != 'solving':
            return
        size = self.size()
        x, y = self.at % size + dx, self.at // size + dy
        while 0 <= x < size and 0 <= y < size:
            cell = y * size + x
            if not self.blocked(cell):
                self.at = cell
                self.down = bool(dy)
                self._redraw()
                return
            x, y = x + dx, y + dy

    def turn(self) -> None:
        """Face the other way, without moving."""
        if self.phase != 'solving':
            return
        self.down = not self.down
        self._redraw()

    def write(self, letter: str) -> None:
        """Put *letter* in the cursor's cell and step on."""
        if self.phase != 'solving' or letter not in LETTERS:
            return
        if self.given(self.at) or self.blocked(self.at):
            return
        if self.filled[self.at] != letter \
                and letter != self.puzzle.solution[self.at]:
            self.mistakes += 1
        self.filled[self.at] = letter
        self._step_on()
        self._settle()

    def erase(self) -> None:
        if self.phase != 'solving' or self.given(self.at):
            return
        self.filled[self.at] = ''
        self._redraw()

    def _step_on(self) -> None:
        """Move to the next cell of this entry, if there is one."""
        slot = self.slot_here()
        if slot is None:
            return
        where = slot.cells.index(self.at)
        if where + 1 < len(slot.cells):
            self.at = slot.cells[where + 1]

    def wrong(self) -> Set[int]:
        """Cells holding a letter that is not the answer's."""
        if self.puzzle is None:
            return set()
        return {cell for cell, letter in enumerate(self.filled)
                if letter and letter != self.puzzle.solution[cell]}

    def _settle(self) -> None:
        if self.puzzle is not None and all(
                self.filled[cell] for cell in range(len(self.filled))
                if self.puzzle.solution[cell]):
            if tuple(self.filled) == self.puzzle.solution:
                self._solved()
            else:
                self.message = _('Full, but not right yet')
        self._redraw()

    def _solved(self) -> None:
        took = self.clock() - self.started_at
        self.results.append((self.rung, self.mistakes, took))
        self.message = (_('Solved in %ds, no slips') % int(took)
                        if not self.mistakes
                        else _('Solved in %ds, %d slips')
                        % (int(took), self.mistakes))
        if self.adaptive:
            if not self.mistakes:
                self.rung = self.clamped(self.rung + 1)
            elif self.mistakes > 4:
                self.rung = self.clamped(self.rung - 1)
        # Green means solved without ever writing a letter that was not
        # the answer's. Finishing is not the measure -- the phase only
        # settles once the grid is full and right, so every solved grid
        # finished. What separates them is having deduced rather than
        # tried the alphabet.
        self.verdict_shown = (not self.mistakes, self.message)
        self.verdict.show(*self.verdict_shown)
        self.phase = 'solved'

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d solved, %d slips, highest level %d') % (
            tally['solved'], tally['slips'], tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        return {
            'solved': len(self.results),
            'slips': sum(slips for _r, slips, _t in self.results),
            'best_rung': max((rung for rung, _s, _t in self.results),
                             default=0),
            'clean': sum(1 for _r, slips, _t in self.results if not slips),
            'seconds': int(sum(took for _r, _s, took in self.results)),
        }

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for shape in self.drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.drawn = []

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.puzzle is not None and self.phase in ('solving', 'solved'):
            self._draw_board()
            self.cluetext.text = self.clue_line() if self.phase == 'solving' \
                else ''
        else:
            self.cluetext.text = ''
        self._update_status()

    def _draw_board(self) -> None:
        left, bottom, side = self._board()
        size = self.size()
        step = side / size
        bad = self.wrong() if self.show_mistakes else set()
        numbers = {slot.cells[0]: slot.number for slot in self.puzzle.slots}

        self.drawn.append(pyglet.shapes.Rectangle(
            left, bottom, side, side, color=self.background,
            batch=self.batch))
        self._light_the_entry(step)
        for cell in range(size * size):
            x, y, _s = self._cell_rect(cell)
            if self.blocked(cell):
                self.drawn.append(pyglet.shapes.Rectangle(
                    x, y, step, step, color=self.block, batch=self.batch))
                continue
            if cell in numbers:
                self.drawn.append(pyglet.text.Label(
                    str(numbers[cell]), font_size=fit(step, 0.16),
                    color=self.ink + (190,), batch=self.batch,
                    x=x + step * 0.08, y=y + step * 0.92,
                    anchor_x='left', anchor_y='top', font_name=FONTLIST))
            letter = self.filled[cell]
            if letter:
                shade = (WRONG if cell in bad
                         else self.ink if self.given(cell) else MINE)
                self.drawn.append(pyglet.text.Label(
                    letter.upper(), font_size=fit(step, 0.46),
                    weight='bold' if self.given(cell) else 'normal',
                    color=shade + (255,), batch=self.batch,
                    x=x + step / 2, y=y + step * 0.44,
                    anchor_x='center', anchor_y='center', font_name=FONTLIST))
        self._draw_rules(left, bottom, side, size, step)

    def _light_the_entry(self, step: float) -> None:
        """A wash over the entry the cursor is in, and a box round it."""
        slot = self.slot_here()
        for cell in (slot.cells if slot else ()):
            x, y, _s = self._cell_rect(cell)
            self.drawn.append(pyglet.shapes.Rectangle(
                x, y, step, step, color=LIT, batch=self.batch))
        if self.hovered is not None and self.hovered != self.at:
            x, y, _s = self._cell_rect(self.hovered)
            self.drawn.append(pyglet.shapes.Rectangle(
                x, y, step, step, color=NEAR, batch=self.batch))
        x, y, _s = self._cell_rect(self.at)
        self.drawn.append(pyglet.shapes.BorderedRectangle(
            x, y, step, step, border=max(2.0, step * 0.08),
            color=self.background, border_color=HERE, batch=self.batch))

    def _draw_rules(self, left: float, bottom: float, side: float,
                    size: int, step: float) -> None:
        for line in range(size + 1):
            at = line * step
            width = max(1.0, step * 0.03)
            self.drawn.append(pyglet.shapes.Line(
                left, bottom + at, left + side, bottom + at,
                thickness=width, color=RULE, batch=self.batch))
            self.drawn.append(pyglet.shapes.Line(
                left + at, bottom, left + at, bottom + side,
                thickness=width, color=RULE, batch=self.batch))

    def _update_status(self) -> None:
        parts = [self.message]
        if self.puzzle is not None and self.phase == 'solving':
            left = sum(1 for cell, letter in enumerate(self.filled)
                       if self.puzzle.solution[cell] and not letter)
            parts.append(_('grid %d/%d   %d left')
                         % (self.trial, self.total_trials, left))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Crossword.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_mouse_motion, self.on_draw)
        Crossword.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'solved':
                self._next_trial()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.F11:
            display.toggle_fullscreen()
            return pyglet.event.EVENT_HANDLED
        # Every letter is a move here, C included, so the options key
        # is O alone rather than the C the rest of the workshop uses.
        if symbol == key.O and self.phase != 'solving':
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.TAB:
            self.turn()
        elif symbol == key.UP:
            self.move(0, -1)
        elif symbol == key.DOWN:
            self.move(0, 1)
        elif symbol == key.LEFT:
            self.move(-1, 0)
        elif symbol == key.RIGHT:
            self.move(1, 0)
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.erase()
        elif key.A <= symbol <= key.Z:
            self.write(LETTERS[symbol - key.A])
        return pyglet.event.EVENT_HANDLED

    def cell_at(self, x: float, y: float) -> Optional[int]:
        """The cell under (*x*, *y*), or ``None`` off the grid."""
        if self.puzzle is None:
            return None
        left, bottom, side = self._board()
        if not (left <= x < left + side and bottom <= y < bottom + side):
            return None
        size = self.size()
        step = side / size
        col = int((x - left) / step)
        row = size - 1 - int((y - bottom) / step)
        if not (0 <= col < size and 0 <= row < size):
            return None
        return row * size + col

    def click(self, cell: int) -> None:
        """Go to *cell*, or turn if that is where the cursor already is.

        Clicking the cell you are on to switch between across and down
        is what every crossword on a screen has done for thirty years.
        Inventing something else here would teach this task's controls
        rather than test anything.
        """
        if self.phase != 'solving' or self.blocked(cell):
            return
        if cell == self.at:
            self.turn()
            return
        self.at = cell
        self._redraw()

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if button == mouse.RIGHT:
            self.turn()
            return pyglet.event.EVENT_HANDLED
        if self.phase in ('ready', 'done'):
            self.start_run()
        elif self.phase == 'solved':
            self._next_trial()
        elif self.phase == 'solving':
            found = self.cell_at(x, y)
            if found is not None:
                self.click(found)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> bool:
        found = self.cell_at(x, y) if self.phase == 'solving' else None
        if found is not None and self.blocked(found):
            found = None
        if found != self.hovered:
            self.hovered = found
            self._redraw()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
