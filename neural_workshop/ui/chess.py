# -*- coding: utf-8 -*-
"""Chess: Winning Move — spot the one move that wins immediately."""
from __future__ import annotations

import random
import time
from typing import List, Optional, Tuple

import chess as chesslib
import pyglet
from pyglet.window import key, mouse

from .. import display, state
from ..chess import Puzzle, generate
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, from_top_edge, width_center
from . import taskoptions
from .verdict import VerdictLabel, above_the_band
from ..i18n import _

LIGHT = (238, 238, 210)
DARK = (118, 150, 86)
SELECT = (246, 194, 62)
TARGET = (120, 188, 210)
WHITE_PIECES = {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'}
BLACK_PIECES = {'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'}


class Chess:
    """Find the winning move. Click a piece, then the square it should move to."""

    instance: Optional['Chess'] = None

    def __init__(self) -> None:
        if Chess.instance is not None:
            Chess.instance.close()
        opts = taskoptions.settings(taskoptions.CHESS)
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.start_rung = int(opts['CHESS_LEVEL'])
        self.total_trials = int(opts['CHESS_TRIALS'])
        self.adaptive = bool(opts['CHESS_ADAPTIVE'])
        self.rung = max(1, min(10, self.start_rung))
        self.trial = 0
        self.results: List[Tuple[int, bool]] = []
        self.phase = 'ready'
        self.selected: Optional[int] = None
        self.puzzle: Optional[Puzzle] = None
        self.position = chesslib.Board.empty()
        self.view_color = chesslib.WHITE
        self.verdict_shown = None
        self.message = _('Press Space to start')
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press, self.on_draw)
        display.register_overlay(self)
        Chess.instance = self

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(_('Winning Move'), font_size=calc_fontsize(22),
            weight='bold', color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(34), anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label('', font_size=calc_fontsize(13),
            color=self.textcolor, batch=self.batch, x=width_center(),
            y=from_top_edge(65), anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     click: move     C: options'),
            font_size=calc_fontsize(11), color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_bottom_edge(24), anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=58)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _board_rect(self) -> Tuple[float, float, float]:
        top = from_top_edge(92)
        bottom = above_the_band(from_bottom_edge(42))
        side = max(80.0, min(state.window.width * .78, top - bottom))
        return ((state.window.width - side) / 2,
                bottom + (top - bottom - side) / 2, side)

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.rung = max(1, min(10, self.start_rung))
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None
        self.selected = None

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self.phase = 'done'
            self.message = _('%d puzzles solved — best level %d') % (
                sum(1 for _, good in self.results if good),
                max((r for r, _ in self.results), default=0))
            self._update_status()
            return
        self.trial += 1
        self.puzzle = generate(self.rung, self.rng)
        self.position = chesslib.Board(self.puzzle.fen)
        self.view_color = self.position.turn
        self.selected = None
        self.verdict_shown = None
        self.verdict.clear()
        self.phase = 'solving'
        side = _('White') if self.position.turn else _('Black')
        self.message = _('Level %d — %s to move and mate in one') % (
            self.rung, side)
        self._redraw()

    def answer(self, source: int, target: int) -> bool:
        if self.phase != 'solving' or self.puzzle is None:
            return False
        move = chesslib.Move(source, target)
        if move not in self.position.legal_moves:
            self.message = _('Illegal move — choose another destination')
            self.selected = None
            self._redraw()
            return False
        self.position.push(move)
        good = self.position.is_checkmate()
        self.results.append((self.rung, good))
        self.phase = 'solved' if good else 'missed'
        if good:
            self.message = _('Checkmate — %s') % self.puzzle.hint
            self.verdict_shown = (True, _('Checkmate'))
            if self.adaptive:
                self.rung = min(10, self.rung + 1)
        else:
            self.message = _('Legal, but not checkmate — the winning move was %s') % (
                self.puzzle.hint)
            self.verdict_shown = (False, _('Missed'))
            if self.adaptive:
                self.rung = max(1, self.rung - 1)
        self.verdict.show(*self.verdict_shown)
        self.selected = None
        self._redraw()
        return good

    def _square_for_display(self, file_: int, rank: int) -> int:
        if self.view_color == chesslib.WHITE:
            return chesslib.square(file_, rank)
        return chesslib.square(7 - file_, 7 - rank)

    def _cell_at(self, x: float, y: float) -> Optional[int]:
        left, bottom, side = self._board_rect()
        if not (left <= x < left + side and bottom <= y < bottom + side):
            return None
        file_ = int((x - left) / (side / 8))
        rank = int((y - bottom) / (side / 8))
        return self._square_for_display(file_, rank)

    def _redraw(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []
        if self.phase in ('solving', 'solved', 'missed'):
            self._draw_board()
        self._update_status()

    def _draw_board(self) -> None:
        left, bottom, side = self._board_rect()
        cell = side / 8
        targets = set()
        if self.selected is not None and self.phase == 'solving':
            targets = {
                move.to_square for move in self.position.legal_moves
                if move.from_square == self.selected
            }
        for rank in range(8):
            for file_ in range(8):
                square = self._square_for_display(file_, rank)
                color = SELECT if square == self.selected else (
                    TARGET if square in targets else
                    (DARK if (file_ + rank) % 2 == 0 else LIGHT))
                self.drawn.append(pyglet.shapes.Rectangle(
                    left + file_ * cell, bottom + rank * cell, cell + 1, cell + 1,
                    color=color, batch=self.batch))
                piece = self.position.piece_at(square)
                if piece:
                    symbol = piece.symbol()
                    glyph = WHITE_PIECES.get(
                        symbol, BLACK_PIECES.get(symbol, symbol))
                    px = left + (file_ + .5) * cell
                    py = bottom + (rank + .5) * cell
                    size = max(18, int(cell * .72))
                    if piece.color == chesslib.WHITE:
                        # Unicode chess glyphs have no stroke support in
                        # pyglet. A dark underlay gives the white pieces a
                        # reliable outline on the cream squares, while the
                        # bright glyph keeps them visually white on dark ones.
                        self.drawn.append(pyglet.text.Label(
                            glyph, font_size=size, color=(38, 38, 38, 255),
                            batch=self.batch, x=px + 1.5, y=py - 1.5,
                            anchor_x='center', anchor_y='center',
                            font_name='DejaVu Sans'))
                        ink = (250, 250, 244, 255)
                    else:
                        ink = (28, 28, 28, 255)
                    self.drawn.append(pyglet.text.Label(
                        glyph, font_size=size, color=ink, batch=self.batch,
                        x=px, y=py, anchor_x='center', anchor_y='center',
                        font_name='DejaVu Sans'))

    def _update_status(self) -> None:
        self.status.text = self.message + (
            _('     puzzle %d/%d') % (self.trial, self.total_trials)
            if self.phase in ('solving', 'solved', 'missed') else '')

    def close(self) -> None:
        if Chess.instance is not self:
            return
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press, self.on_draw)
        Chess.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> bool:
        if button != mouse.LEFT or self.phase != 'solving':
            return pyglet.event.EVENT_HANDLED
        cell = self._cell_at(x, y)
        if cell is None:
            return pyglet.event.EVENT_HANDLED
        if self.selected is None:
            if self.position.color_at(cell) == self.position.turn:
                self.selected = cell
                self._redraw()
        else:
            if self.position.color_at(cell) == self.position.turn:
                self.selected = cell
                self._redraw()
            else:
                self.answer(self.selected, cell)
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase in ('solved', 'missed'):
                self._next_trial()
        elif symbol == key.C:
            taskoptions.open_task_options('chess')
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['Chess']
