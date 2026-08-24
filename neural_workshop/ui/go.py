# -*- coding: utf-8 -*-
"""A Go tsumego screen: find the one move that captures the marked group."""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, state
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, from_top_edge, width_center
from ..go import GoProblem, generate_problem, play
from ..i18n import _
from . import cursor
from .verdict import VerdictLabel, above_the_band


class GoWinningMove:
    """Place one Black stone on White's final liberty."""

    instance: Optional['GoWinningMove'] = None

    def __init__(self) -> None:
        if GoWinningMove.instance is not None:
            GoWinningMove.instance.close()
        self.rng = random.Random()
        self.start_difficulty = 1
        self.total_trials = 10
        self.difficulty = 1
        self.cursor_x = 0
        self.cursor_y = 0
        self.trial = 0
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
            _('Esc: menu     1-0: difficulty     Space: start     click a point or use arrows + Enter'),
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
        bottom = above_the_band(from_bottom_edge(44))
        side = min(state.window.width * .82, top - bottom)
        return (width_center() - side / 2, bottom + (top - bottom - side) / 2,
                side / max(1, size - 1))

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
            left - step * .55, bottom - step * .55, board_side + step * 1.1,
            board_side + step * 1.1, color=(219, 174, 92), batch=self.batch))
        for i in range(size):
            self.drawn.append(pyglet.shapes.Line(
                left, bottom + i * step, left + board_side, bottom + i * step,
                color=(35, 35, 35), batch=self.batch))
            self.drawn.append(pyglet.shapes.Line(
                left + i * step, bottom, left + i * step, bottom + board_side,
                color=(35, 35, 35), batch=self.batch))
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
        self.status.text = _('%s — problem %d of %d') % (
            _('Black to play'), self.trial, self.total_trials)

    def _reset(self) -> None:
        self.trial = 0
        self.problem = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None
        self.verdict.clear()

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def set_difficulty(self, difficulty: int) -> None:
        if self.phase in ('ready', 'done'):
            self.difficulty = max(1, min(10, difficulty))
            self.message = _('Press Space to start')
            self._redraw()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self.phase = 'done'
            self.message = _('Run complete')
            self._redraw()
            return
        self.trial += 1
        self.problem = generate_problem(self.rng.randrange(1 << 30), self.difficulty)
        self.phase = 'solving'
        self.verdict_shown = None
        self.verdict.clear()
        self._redraw()

    def answer(self, port: int) -> None:
        if self.phase != 'solving' or not self.problem:
            return
        size = self.problem.size
        point = (port % size, port // size)
        if port >= size * size:
            return
        if point == self.problem.winning_move:
            after = play(self.problem.board, point, 1)
            self.problem = GoProblem(size, after,
                                     self.problem.target, point,
                                     self.problem.difficulty)  # type: ignore[arg-type]
            self.phase = 'solved'
            self.verdict_shown = (True, _('Winning move!'))
            self.verdict.show(*self.verdict_shown)
        else:
            self.phase = 'failed'
            self.verdict_shown = (False, _('That move does not capture the group'))
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
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
