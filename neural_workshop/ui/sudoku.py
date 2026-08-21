# -*- coding: utf-8 -*-
"""The Sudoku screen: arrows move, digits fill, N pencils.

The reasoning lives in :mod:`neural_workshop.sudoku`; this module is
the grid drawn and the keys that fill it. Three decisions matter here:

* **Pencil marks are not a luxury.** A puzzle whose rung is measured
  in fish and forced chains cannot be held in the head cell by cell,
  and a screen that made you do so would be testing handwriting rather
  than reasoning. ``N`` swaps the digits between filling a cell and
  pencilling a candidate into it, which is how the hard rungs are
  meant to be played at all.

* **Givens are not editable and are drawn as such.** The one thing a
  sudoku screen must never do is let the puzzle be argued with. A
  given is dimmer, heavier, and refuses the keystroke.

* **A wrong digit is shown as wrong only if you ask.** With conflicts
  turned on, a cell that clashes with one of its peers is marked at
  once, which turns the hard rungs into something a person can finish;
  turned off, nothing is checked until the grid is full, which is the
  real game. It is one option and it changes the task, so the options
  note says so rather than leaving it to be discovered.

Sixteens run on 1-9 and then A-G, and the same key does the same thing
at every size.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Set, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (MAX_FONT_SIZE, calc_fontsize, from_bottom_edge,
                        from_top_edge, width_center)
from ..sudoku import GRADES, Puzzle, TECHNIQUES, generate, peers
from . import cursor, taskoptions
from ..i18n import _

#: The lines between boxes, and the lighter ones between cells.
RULE = (120, 120, 120)
#: Where the cursor is, and the cell it came from.
HERE = (86, 180, 233)          # sky blue
#: A digit that clashes with one of its peers, when clashes are shown.
CLASH = (213, 94, 0)           # vermilion
#: What the player has written, as against what came with the puzzle.
MINE = (0, 114, 178)           # blue
#: The wash behind cells sharing a row, column or box with the cursor.
LIT = (86, 180, 233, 40)

#: Digits past nine are letters, which is what a sixteen needs.
GLYPHS = '123456789ABCDEFG'


def fit(step: float, share: float) -> float:
    """A font size taken from the cell rather than from the window.

    :func:`~neural_workshop.geometry.calc_fontsize` scales a
    *reference* size by the window height, which is right for the
    chrome and wrong here: a cell is already measured in this
    window's pixels, so putting it through that would scale it
    twice and a big window would spill digits out of their cells.
    """
    return max(5.0, min(MAX_FONT_SIZE, step * share))


def glyph(value: int) -> str:
    """How a digit is written: 1-9, then A-G."""
    return GLYPHS[value - 1] if 1 <= value <= len(GLYPHS) else ''


class Sudoku:
    """Fill the grid. Arrows move, digits write, N pencils, Esc leaves."""

    instance: Optional['Sudoku'] = None

    def __init__(self) -> None:
        if Sudoku.instance is not None:
            Sudoku.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.puzzle: Optional[Puzzle] = None
        self.filled: List[int] = []
        self.marks: Dict[int, int] = {}
        self.at = 0
        self.pencil = False
        self.mistakes = 0
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, int, float]] = []   # rung, slips, secs
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        Sudoku.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SUDOKU)
        self.start_rung = int(opts['SUDOKU_LEVEL'])
        self.total_trials = int(opts['SUDOKU_TRIALS'])
        self.show_clashes = bool(opts['SUDOKU_SHOW_CLASHES'])
        self.adaptive = bool(opts['SUDOKU_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('sudoku', on_apply=self.apply_options)

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
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Sudoku'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(64),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     arrows: move'
              '     digits: write     N: pencil     O: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def size(self) -> int:
        return self.puzzle.size if self.puzzle is not None else 1

    def _board(self) -> Tuple[float, float, float]:
        """Left, bottom and side of the whole board on screen."""
        window = state.window
        top = from_top_edge(84)
        bottom = from_bottom_edge(44)
        side = max(40.0, min(window.width * 0.86, top - bottom))
        return ((window.width - side) / 2, bottom + (top - bottom - side) / 2,
                side)

    def _cell_rect(self, cell: int) -> Tuple[float, float, float]:
        left, bottom, side = self._board()
        step = side / self.size()
        x, y = cell % self.size(), cell // self.size()
        return (left + x * step,
                bottom + (self.size() - 1 - y) * step, step)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.puzzle = None
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.puzzle = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self.filled = list(self.puzzle.givens)
        self.marks = {}
        self.at = next((c for c, v in enumerate(self.filled) if not v), 0)
        self.pencil = False
        self.mistakes = 0
        self.started_at = self.clock()
        self.phase = 'solving'
        grade = GRADES[self.rung - 1]
        self.message = _('%s — %s, %d to fill') % (
            _(grade.name), _(TECHNIQUES[self.puzzle.tier]),
            self.puzzle.blanks())
        self._redraw()

    def given(self, cell: int) -> bool:
        """Whether *cell* came with the puzzle and cannot be changed."""
        return bool(self.puzzle) and bool(self.puzzle.givens[cell])

    # --- playing ---------------------------------------------------------

    def move(self, dx: int, dy: int) -> None:
        if self.phase != 'solving':
            return
        size = self.size()
        x, y = self.at % size + dx, self.at // size + dy
        if 0 <= x < size and 0 <= y < size:
            self.at = y * size + x
            self._redraw()

    def write(self, value: int) -> None:
        """Put *value* in the cursor's cell, or pencil it in."""
        if self.phase != 'solving' or value > self.size():
            return
        if self.given(self.at):
            self.message = _('That one came with the puzzle')
            self._update_status()
            return
        if self.pencil:
            self.marks[self.at] = self.marks.get(self.at, 0) ^ (
                1 << (value - 1))
            self._redraw()
            return
        if self.filled[self.at] == value:
            value = 0                    # writing it twice rubs it out
        self.filled[self.at] = value
        if value:
            self.marks.pop(self.at, None)
            if value != self.puzzle.solution[self.at]:
                self.mistakes += 1
        self._settle()

    def erase(self) -> None:
        if self.phase != 'solving' or self.given(self.at):
            return
        if self.pencil:
            self.marks.pop(self.at, None)
        else:
            self.filled[self.at] = 0
        self._redraw()

    def toggle_pencil(self) -> None:
        if self.phase != 'solving':
            return
        self.pencil = not self.pencil
        self.message = (_('Pencilling') if self.pencil
                        else _('Writing'))
        self._redraw()

    def clashes(self) -> Set[int]:
        """Cells holding a digit one of their peers already holds."""
        found: Set[int] = set()
        if self.puzzle is None:
            return found
        near = peers(self.puzzle.box)
        for cell, value in enumerate(self.filled):
            if not value:
                continue
            for other in near[cell]:
                if self.filled[other] == value:
                    found.add(cell)
                    found.add(other)
        return found

    def _settle(self) -> None:
        if all(self.filled):
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
        self.phase = 'solved'

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d solved, %d slips, highest rung %d') % (
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
        self._update_status()

    def _draw_board(self) -> None:
        left, bottom, side = self._board()
        size = self.size()
        box = self.puzzle.box
        step = side / size
        wrong = self.clashes() if self.show_clashes else set()

        self.drawn.append(pyglet.shapes.Rectangle(
            left, bottom, side, side, color=self.background,
            batch=self.batch))
        self._light_the_cursor(step)
        for cell, value in enumerate(self.filled):
            x, y, _s = self._cell_rect(cell)
            if value:
                shade = (CLASH if cell in wrong
                         else self.ink if self.given(cell) else MINE)
                self.drawn.append(pyglet.text.Label(
                    glyph(value), font_size=fit(step, 0.34),
                    weight='bold' if self.given(cell) else 'normal',
                    color=shade + (255,), batch=self.batch,
                    x=x + step / 2, y=y + step / 2,
                    anchor_x='center', anchor_y='center',
                    font_name=FONTLIST))
            elif self.marks.get(cell):
                self._draw_marks(cell, x, y, step, box)
        self._draw_rules(left, bottom, side, size, box, step)

    def _light_the_cursor(self, step: float) -> None:
        """A wash over what the cursor can see, and a box round it."""
        near = peers(self.puzzle.box)[self.at]
        for cell in near:
            x, y, _s = self._cell_rect(cell)
            self.drawn.append(pyglet.shapes.Rectangle(
                x, y, step, step, color=LIT, batch=self.batch))
        x, y, _s = self._cell_rect(self.at)
        self.drawn.append(pyglet.shapes.BorderedRectangle(
            x, y, step, step, border=max(2.0, step * 0.08),
            color=self.background, border_color=HERE, batch=self.batch))

    def _draw_marks(self, cell: int, x: float, y: float, step: float,
                    box: int) -> None:
        """Pencilled candidates, laid out the way the box is."""
        held = self.marks.get(cell, 0)
        for slot in range(self.size()):
            if not held >> slot & 1:
                continue
            row, col = slot // box, slot % box
            self.drawn.append(pyglet.text.Label(
                glyph(slot + 1), font_size=fit(step, 0.13),
                color=self.ink + (170,), batch=self.batch,
                x=x + step * (col + 0.5) / box,
                y=y + step * (box - row - 0.5) / box,
                anchor_x='center', anchor_y='center', font_name=FONTLIST))

    def _draw_rules(self, left: float, bottom: float, side: float,
                    size: int, box: int, step: float) -> None:
        """Thin lines between cells, thick ones between boxes."""
        for line in range(size + 1):
            heavy = line % box == 0
            width = max(1.0, step * (0.06 if heavy else 0.02))
            shade = self.ink if heavy else RULE
            at = line * step
            self.drawn.append(pyglet.shapes.Line(
                left, bottom + at, left + side, bottom + at,
                thickness=width, color=shade, batch=self.batch))
            self.drawn.append(pyglet.shapes.Line(
                left + at, bottom, left + at, bottom + side,
                thickness=width, color=shade, batch=self.batch))

    def _update_status(self) -> None:
        parts = [self.message]
        if self.puzzle is not None and self.phase == 'solving':
            left = sum(1 for v in self.filled if not v)
            parts.append(_('puzzle %d/%d   %d left')
                         % (self.trial, self.total_trials, left))
            if self.pencil:
                parts.append(_('pencil'))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Sudoku.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        Sudoku.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    #: Number row and keypad for 1-9, letters for 10-16.
    _DIGIT_KEYS = {
        key._1: 1, key._2: 2, key._3: 3, key._4: 4, key._5: 5, key._6: 6,
        key._7: 7, key._8: 8, key._9: 9,
        key.NUM_1: 1, key.NUM_2: 2, key.NUM_3: 3, key.NUM_4: 4, key.NUM_5: 5,
        key.NUM_6: 6, key.NUM_7: 7, key.NUM_8: 8, key.NUM_9: 9,
        key.A: 10, key.B: 11, key.C: 12, key.D: 13, key.E: 14, key.F: 15,
        key.G: 16,
    }

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
        # C is the options key everywhere else in the workshop and
        # also the digit twelve; on a board that goes that high the
        # board wins, so O opens the options at every size and C
        # only at the sizes where it is not a digit.
        if symbol == key.O or (symbol == key.C and self.size() < 12):
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.N:
            self.toggle_pencil()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.UP:
            self.move(0, -1)
        elif symbol == key.DOWN:
            self.move(0, 1)
        elif symbol == key.LEFT:
            self.move(-1, 0)
        elif symbol == key.RIGHT:
            self.move(1, 0)
        elif symbol in (key.BACKSPACE, key.DELETE, key._0, key.NUM_0):
            self.erase()
        elif symbol in self._DIGIT_KEYS:
            self.write(self._DIGIT_KEYS[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
