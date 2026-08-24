# -*- coding: utf-8 -*-
"""The N-in-a-row puzzle screen.

The board is a scenario, not a match against the computer.  Blue is the
player's pellet, orange is the opponent's, and one cell completes a line of
five.  A person steers a highlighted cell or clicks it, then presses Enter;
the agent boundary calls :meth:`choose` with the flat cell id directly.

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
from ..geometry import calc_fontsize, from_bottom_edge, from_top_edge, width_center
from ..i18n import _
from ..ninarow import EMPTY, OPPONENT, PLAYER, Puzzle, generate, grade_at
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

PLAYER_COLOUR = (0, 114, 178)
OPPONENT_COLOUR = (213, 94, 0)
GRID_COLOUR = (128, 128, 128)
SELECT_COLOUR = (232, 178, 0)


class NInARow:
    """Find the cell that completes five in a row."""

    instance: Optional['NInARow'] = None

    def __init__(self) -> None:
        if NInARow.instance is not None:
            NInARow.instance.close()
        self.rng = random.Random()
        #: Replaced by a stepped environment's virtual clock.
        self.clock = time.time
        self.puzzle: Optional[Puzzle] = None
        self.choice = 0
        self.started_at = 0.0
        self.trial = 0
        self.results: List[Tuple[int, bool, float]] = []
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
        NInARow.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.NINAROW)
        self.start_rung = int(opts['NINAROW_LEVEL'])
        self.total_trials = int(opts['NINAROW_TRIALS'])
        self.grid_size = int(opts['NINAROW_GRID'])
        self.pellets = int(opts['NINAROW_PELLETS'])
        self.show_answer = bool(opts['NINAROW_SHOW_ANSWER'])
        self.adaptive = bool(opts['NINAROW_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(8, int(rung)))

    def open_options(self) -> None:
        taskoptions.open_task_options('n_in_a_row',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _floor(self) -> float:
        """The board's bottom edge, above the public verdict band."""
        return above_the_band(from_bottom_edge(56))

    def _board_box(self) -> Tuple[float, float, float]:
        """Return left, bottom and side for the current board."""
        bottom = self._floor() + 8
        top = from_top_edge(132)
        side = min(state.window.width * 0.82, max(80.0, top - bottom))
        return width_center() - side / 2.0, bottom, side

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            _('N-in-a-row'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34), anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(64),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.note = pyglet.text.Label(
            '', font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(88),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start   arrows/click: choose'
              '   Enter: answer   O: options'),
            font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _cell_box(self, cell: int) -> Tuple[float, float, float]:
        left, bottom, side = self._board_box()
        size = self.puzzle.size if self.puzzle is not None else grade_at(self.rung).size
        step = side / size
        row, col = divmod(cell, size)
        return left + col * step, bottom + (size - row - 1) * step, step

    def _draw_board(self) -> None:
        self._clear_drawn()
        if self.puzzle is None:
            return
        left, bottom, side = self._board_box()
        size = self.puzzle.size
        step = side / size
        # A quiet board background makes the two pellets readable in either
        # theme, while all board art remains above the verdict band.
        self.drawn.append(pyglet.shapes.Rectangle(
            left, bottom, side, side, color=(236, 236, 236),
            batch=self.batch))
        for row in range(size + 1):
            y = bottom + row * step
            self.drawn.append(pyglet.shapes.Line(
                left, y, left + side, y, thickness=1, color=GRID_COLOUR,
                batch=self.batch))
        for col in range(size + 1):
            x = left + col * step
            self.drawn.append(pyglet.shapes.Line(
                x, bottom, x, bottom + side, thickness=1, color=GRID_COLOUR,
                batch=self.batch))
        radius = max(2.0, step * 0.32)
        for cell, value in enumerate(self.puzzle.cells):
            if value == EMPTY:
                continue
            x, y, _step = self._cell_box(cell)
            colour = PLAYER_COLOUR if value == PLAYER else OPPONENT_COLOUR
            self.drawn.append(pyglet.shapes.Circle(
                x + step / 2, y + step / 2, radius, color=colour,
                batch=self.batch))
        marked = None
        marked_colour = SELECT_COLOUR
        if self.phase == 'asking':
            marked = self.choice
        elif self.phase == 'judged' and self.show_answer:
            marked = self.puzzle.answer
            marked_colour = (0, 158, 115)
        if marked is not None:
            x, y, _step = self._cell_box(marked)
            margin = max(2.0, step * 0.08)
            self.drawn.extend((
                pyglet.shapes.Line(x + margin, y + margin,
                                   x + step - margin, y + margin,
                                   thickness=2, color=marked_colour,
                                   batch=self.batch),
                pyglet.shapes.Line(x + step - margin, y + margin,
                                   x + step - margin, y + step - margin,
                                   thickness=2, color=marked_colour,
                                   batch=self.batch),
                pyglet.shapes.Line(x + step - margin, y + step - margin,
                                   x + margin, y + step - margin,
                                   thickness=2, color=marked_colour,
                                   batch=self.batch),
                pyglet.shapes.Line(x + margin, y + step - margin,
                                   x + margin, y + margin,
                                   thickness=2, color=marked_colour,
                                   batch=self.batch)))

    def relayout(self) -> None:
        """Rebuild window-sized labels and board geometry after resizing."""
        self._build_chrome()

    # --- run -------------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.puzzle = None
        self.choice = 0
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
        self.puzzle = generate(
            self.rung, seed=self.rng.randrange(1 << 30),
            size=self.grid_size or None, pellets=self.pellets or None)
        if self.puzzle is None:
            self.phase = 'done'
            self.message = _('No unique position at this setting')
            self._redraw()
            return
        self.choice = next((cell for cell, value in enumerate(self.puzzle.cells)
                            if value == EMPTY), 0)
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'asking'
        self.message = _('Find the move that makes five')
        self._redraw()

    # --- interaction -----------------------------------------------------

    def move(self, dr: int, dc: int) -> None:
        if self.phase != 'asking' or self.puzzle is None:
            return
        row, col = divmod(self.choice, self.puzzle.size)
        row = max(0, min(self.puzzle.size - 1, row + int(dr)))
        col = max(0, min(self.puzzle.size - 1, col + int(dc)))
        self.choice = row * self.puzzle.size + col
        self._redraw()

    def choose(self, cell: int) -> None:
        """Answer with a flat cell id; out-of-board ports do nothing."""
        if self.phase != 'asking' or self.puzzle is None:
            return
        if not 0 <= int(cell) < self.puzzle.area:
            return
        if self.puzzle.cells[int(cell)] != EMPTY:
            return
        self.choice = int(cell)
        self._judge()

    def submit(self) -> None:
        if self.phase == 'asking':
            self.choose(self.choice)

    def _judge(self) -> None:
        took = self.clock() - self.started_at
        right = self.choice == self.puzzle.answer
        self.results.append((self.rung, right, took))
        self.message = _('Right') if right else _('Not that cell')
        if self.adaptive:
            self.rung = self.clamped(self.rung + (1 if right else -1))
        self.verdict_shown = (right, self.message)
        self.verdict.show(right, _('Right') if right else _('No'))
        self.phase = 'judged'
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        score = self.score()
        self.message = _('%d of %d right, highest level %d') % (
            score['right'], score['asked'], score['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        return {
            'asked': len(self.results),
            'right': sum(1 for _rung, right, _took in self.results if right),
            'best_rung': max((rung for rung, right, _took in self.results
                              if right), default=0),
            'seconds': int(sum(took for _rung, _right, took in self.results)),
        }

    # --- redraw and lifecycle -------------------------------------------

    def _redraw(self) -> None:
        if self.puzzle is None:
            self.note.text = _('The board grows from 5 to 19 squares.')
        else:
            self.note.text = _('%d x %d board   %d pellets   five to win') % (
                self.puzzle.size, self.puzzle.size, self.puzzle.pellets)
        if self.phase == 'asking':
            self.status.text = '%s     %s' % (
                self.message, _('question %d/%d') %
                (self.trial, self.total_trials))
        else:
            self.status.text = self.message
        self._draw_board()

    def advance(self) -> None:
        if self.phase in ('ready', 'done'):
            self.start_run()
        elif self.phase == 'judged':
            self._next_trial()

    def close(self) -> None:
        if NInARow.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        NInARow.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='planning')

    # --- events ----------------------------------------------------------

    def _cell_at_pixel(self, x: float, y: float) -> Optional[int]:
        if self.puzzle is None:
            return None
        left, bottom, side = self._board_box()
        if not left <= x < left + side or not bottom <= y < bottom + side:
            return None
        size = self.puzzle.size
        col = int((x - left) / (side / size))
        row_from_bottom = int((y - bottom) / (side / size))
        row = size - 1 - row_from_bottom
        return row * size + col

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
            if symbol == key.UP:
                self.move(-1, 0)
            elif symbol == key.DOWN:
                self.move(1, 0)
            elif symbol == key.LEFT:
                self.move(0, -1)
            elif symbol == key.RIGHT:
                self.move(0, 1)
            elif symbol in (key.ENTER, key.RETURN, key.NUM_ENTER):
                self.submit()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'asking':
            cell = self._cell_at_pixel(x, y)
            if cell is not None:
                self.choice = cell
                self._redraw()
        else:
            self.advance()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['NInARow']
