# -*- coding: utf-8 -*-
"""The Go winning-move screen, from guided atari to full-board scans."""
from __future__ import annotations

import random
import time
from dataclasses import replace
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, state
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, from_top_edge, width_center
from ..go import GoProblem, capture_moves, generate_problem, play
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band


class GoWinningMove:
    """Place one Black stone on White's final liberty."""

    instance: Optional['GoWinningMove'] = None

    def __init__(self) -> None:
        if GoWinningMove.instance is not None:
            GoWinningMove.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self._read_options()
        self.difficulty = max(1, min(10, self.start_difficulty))
        self.cursor_x = 0
        self.cursor_y = 0
        self.trial = 0
        self.correct = 0
        self.problem: Optional[GoProblem] = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        GoWinningMove.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.GO_WINNING_MOVE)
        self.start_difficulty = int(opts['GO_LEVEL'])
        self.total_trials = int(opts['GO_TRIALS'])

    def open_options(self) -> None:
        taskoptions.open_task_options('go_winning_move',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        """Take the new dials and put the run back to the start.

        Rather than letting them wait until the task is next opened,
        which is what a screen with no ``on_apply`` does. A level row
        that visibly does nothing is worse than no row.
        """
        self._read_options()
        self._reset()
        self.difficulty = max(1, min(10, self.start_difficulty))
        self._build_chrome()

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Find the Winning Move'), font_size=calc_fontsize(22),
            weight='bold', color=(fg, fg, fg, 255), batch=self.batch,
            x=width_center(), y=from_top_edge(34), anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(13), color=(fg, fg, fg, 255),
            batch=self.batch, x=width_center(), y=from_top_edge(64),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   1-0: level   Space: start/next'
              '   click, or arrows + Enter   C: options'),
            font_size=calc_fontsize(11), color=(fg, fg, fg, 255),
            batch=self.batch, x=width_center(), y=from_bottom_edge(24),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _board(self) -> Tuple[float, float, float]:
        size = self.problem.size if self.problem else 9
        top = from_top_edge(90)
        floor = above_the_band(from_bottom_edge(44))
        outer = min(state.window.width * .82, top - floor)
        step = outer / size
        grid_side = step * (size - 1)
        return (width_center() - grid_side / 2,
                floor + (outer - grid_side) / 2, step)

    def _point(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        if not self.problem:
            return None
        left, bottom, step = self._board()
        px = round((x - left) / step)
        py = round((y - bottom) / step)
        size = self.problem.size
        if 0 <= px < size and 0 <= py < size and abs(x - (left + px * step)) < step * .42 and abs(y - (bottom + py * step)) < step * .42:
            return px, size - 1 - py
        return None

    def _redraw(self) -> None:
        for item in self.drawn:
            item.delete()
        self.drawn = []
        if not self.problem:
            self.status.text = _('%s — difficulty %d/10') % (self.message, self.difficulty)
            return
        size = self.problem.size
        left, bottom, step = self._board()
        board_side = step * (size - 1)
        self.drawn.append(pyglet.shapes.Rectangle(
            left - step * .5, bottom - step * .5, board_side + step,
            board_side + step, color=(219, 174, 92), batch=self.batch))
        for i in range(size):
            self.drawn.append(pyglet.shapes.Line(
                left, bottom + i * step, left + board_side, bottom + i * step,
                color=(35, 35, 35), batch=self.batch))
            self.drawn.append(pyglet.shapes.Line(
                left + i * step, bottom, left + i * step, bottom + board_side,
                color=(35, 35, 35), batch=self.batch))
        if self.problem.show_target and self.phase == 'solving':
            for x, y in self.problem.target:
                self.drawn.append(pyglet.shapes.Circle(
                    left + x * step, bottom + (size - 1 - y) * step,
                    step * .49, color=(50, 120, 220), batch=self.batch))
        if self.problem.show_move and self.phase == 'solving':
            x, y = self.problem.winning_move
            self.drawn.append(pyglet.shapes.Circle(
                left + x * step, bottom + (size - 1 - y) * step,
                step * .13, color=(50, 120, 220), batch=self.batch))
        for y, row in enumerate(self.problem.board):
            for x, stone in enumerate(row):
                if not stone:
                    continue
                color = (25, 25, 28) if stone == 1 else (238, 238, 238)
                self.drawn.append(pyglet.shapes.Circle(
                    left + x * step, bottom + (size - 1 - y) * step,
                    step * .43, color=color, batch=self.batch))
        if self.phase == 'solving':
            self.drawn.append(pyglet.shapes.BorderedRectangle(
                left + self.cursor_x * step - step * .13,
                bottom + (size - 1 - self.cursor_y) * step - step * .13,
                step * .26, step * .26, border=max(1.0, step * .05),
                color=(219, 174, 92, 0), border_color=(50, 120, 220),
                batch=self.batch))
        if self.phase == 'solving':
            objective = (_('capture the blue-ringed White group')
                         if self.problem.show_target else
                         _('capture the largest White group'))
            self.status.text = _(
                'Level %d/10 — Black to play: %s — problem %d/%d') % (
                    self.difficulty, objective, self.trial, self.total_trials)
        else:
            self.status.text = self.message

    def _reset(self) -> None:
        self.trial = 0
        self.correct = 0
        self.problem = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None
        self.verdict.clear()

    def start_run(self) -> None:
        self._reset()
        self.difficulty = max(1, min(10, int(self.start_difficulty)))
        self._next_trial()

    def set_difficulty(self, difficulty: int) -> None:
        if self.phase in ('ready', 'done'):
            self.difficulty = max(1, min(10, difficulty))
            self.start_difficulty = self.difficulty
            self.message = _('Press Space to start')
            self._redraw()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self.phase = 'done'
            self.problem = None
            self.message = _('%d of %d winning moves found') % (
                self.correct, self.total_trials)
            self._redraw()
            return
        self.trial += 1
        self.problem = generate_problem(self.rng.randrange(1 << 30), self.difficulty)
        self.cursor_x = self.problem.size // 2
        self.cursor_y = self.problem.size // 2
        self.phase = 'solving'
        self.verdict_shown = None
        self.verdict.clear()
        self._redraw()

    def answer(self, port: int) -> None:
        if self.phase != 'solving' or not self.problem:
            return
        size = self.problem.size
        point = (port % size, port // size)
        if port < 0 or port >= size * size:
            return
        captures = capture_moves(self.problem.board)
        if point == self.problem.winning_move:
            after = play(self.problem.board, point, 1)
            if after is None:                         # generator invariant
                raise RuntimeError('winning Go move became illegal')
            self.problem = replace(self.problem, board=after)
            self.phase = 'solved'
            self.correct += 1
            self.message = _('Winning move — captured %d stones') % (
                captures[point])
            self.verdict_shown = (True, self.message)
            self.verdict.show(*self.verdict_shown)
        else:
            self.phase = 'failed'
            caught = captures.get(point, 0)
            if caught:
                self.message = _(
                    'Captured %d, but the winning move captures %d') % (
                        caught, self.problem.capture_goal)
            elif self.problem.board[point[1]][point[0]]:
                self.message = _('That intersection is occupied')
            else:
                self.message = _('That move captures no White stones')
            self.verdict_shown = (False, self.message)
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.SPACE and self.phase in ('solved', 'failed'):
            self._next_trial()
        elif symbol == key.ENTER and self.phase == 'solving':
            self.answer(self.cursor_y * (self.problem.size if self.problem else 1) + self.cursor_x)
        elif symbol == key.LEFT and self.phase == 'solving':
            self.cursor_x = max(0, self.cursor_x - 1)
        elif symbol == key.RIGHT and self.phase == 'solving' and self.problem:
            self.cursor_x = min(self.problem.size - 1, self.cursor_x + 1)
        elif symbol == key.UP and self.phase == 'solving':
            self.cursor_y = max(0, self.cursor_y - 1)
        elif symbol == key.DOWN and self.phase == 'solving' and self.problem:
            self.cursor_y = min(self.problem.size - 1, self.cursor_y + 1)
        elif self.phase in ('ready', 'done'):
            number_keys = {
                key._1: 1, key._2: 2, key._3: 3, key._4: 4, key._5: 5,
                key._6: 6, key._7: 7, key._8: 8, key._9: 9, key._0: 10,
            }
            if symbol in number_keys:
                self.set_difficulty(number_keys[symbol])
        if self.phase == 'solving' and self.problem:
            self._redraw()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> bool:
        if button == mouse.LEFT:
            point = self._point(x, y)
            if point is not None:
                self.answer(point[1] * self.problem.size + point[0])
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED

    def close(self) -> None:
        try:
            state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                         self.on_draw)
        except Exception:
            pass
        display.unregister_overlay(self)
        cursor.release()
        if GoWinningMove.instance is self:
            GoWinningMove.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')


__all__ = ['GoWinningMove']
