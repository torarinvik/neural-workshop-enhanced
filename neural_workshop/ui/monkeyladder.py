# -*- coding: utf-8 -*-
"""Monkey Ladder: remember numbered tiles and click them in order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import state
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, from_top_edge, width_center
from . import taskoptions
from ..i18n import _

GridCell = Tuple[int, int]


class MonkeyLadder:
    """A Corsi-style numbered grid. Space starts a round; Esc returns."""

    instance: Optional['MonkeyLadder'] = None

    def __init__(self) -> None:
        if MonkeyLadder.instance is not None:
            MonkeyLadder.instance.close()
        self.grid = 5
        self.level = 3
        self._read_options()
        self.phase = 'ready'
        self.sequence: List[GridCell] = []
        self.next_index = 0
        self.clicked: List[GridCell] = []
        self.wrong: Optional[GridCell] = None
        self.show_until = 0.0
        self.message = _('Press Space to watch the numbers')
        self.batch = pyglet.graphics.Batch()
        self.shapes: List[object] = []
        self.cell_labels: List[pyglet.text.Label] = []
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.title = pyglet.text.Label(
            _('Monkey Ladder'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: next round     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(30),
            anchor_x='center', anchor_y='center')
        self._layout_grid()
        self._redraw()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        try:
            state.window.set_mouse_visible(True)
        except Exception:
            pass
        MonkeyLadder.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        """Load this task's settings from the config."""
        opts = taskoptions.settings(taskoptions.MONKEY_LADDER)
        self.grid = int(opts['MONKEY_LADDER_GRID'])
        self.start_level = int(opts['MONKEY_LADDER_START_LENGTH'])
        self.adaptive = bool(opts['MONKEY_LADDER_ADAPTIVE'])
        self.show_ms = int(opts['MONKEY_LADDER_SHOW_MS'])
        self.per_tile_ms = int(opts['MONKEY_LADDER_PER_TILE_MS'])
        self.reveal_answer = bool(opts['MONKEY_LADDER_REVEAL_ANSWER'])
        self.level = min(max(2, self.start_level), self.grid * self.grid)

    def open_options(self) -> None:
        """Show this task's settings screen."""
        taskoptions.open_task_options('monkey_ladder',
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        """Re-read the settings and start a fresh round from scratch."""
        self._read_options()
        self.phase = 'ready'
        self.sequence = []
        self.clicked = []
        self.wrong = None
        self.next_index = 0
        self.message = _('Press Space to watch the numbers')
        self._layout_grid()
        self._redraw()

    def _layout_grid(self) -> None:
        window = state.window
        size = min(window.width, window.height) * 0.62
        self.cell = size / self.grid
        self.origin_x = (window.width - size) / 2
        self.origin_y = (window.height - size) / 2 - 10

    def cell_at(self, x: float, y: float) -> Optional[GridCell]:
        col = int((x - self.origin_x) // self.cell)
        row = int((y - self.origin_y) // self.cell)
        if 0 <= col < self.grid and 0 <= row < self.grid:
            return row, col
        return None

    def start_round(self) -> None:
        cells = [(r, c) for r in range(self.grid) for c in range(self.grid)]
        count = min(self.level, len(cells))
        self.sequence = random.sample(cells, count)
        self.next_index = 0
        self.clicked = []
        self.wrong = None
        self.phase = 'show'
        self.show_until = time.time() + (self.show_ms
                                         + self.per_tile_ms * count) / 1000.
        self.message = _('Remember the order')
        self._redraw()

    def update(self, dt: float) -> None:
        if self.phase == 'show' and time.time() >= self.show_until:
            self.phase = 'input'
            self.message = _('Click 1 through %d') % len(self.sequence)
            self._redraw()

    def click_cell(self, cell: GridCell) -> None:
        """Handle a click on *cell*. Used by the mouse handler and tests."""
        if self.phase != 'input' or cell in self.clicked:
            return
        expected = self.sequence[self.next_index]
        if cell == expected:
            self.clicked.append(cell)
            self.next_index += 1
            if self.next_index >= len(self.sequence):
                if self.adaptive:
                    self.level = min(self.grid * self.grid, self.level + 1)
                self.phase = 'result'
                self.message = (_('Correct — next length %d') % self.level
                                if self.adaptive else _('Correct'))
        else:
            self.wrong = cell
            if self.adaptive:
                self.level = max(2, self.level - 1)
            self.phase = 'result'
            self.message = (_('Miss — back to length %d') % self.level
                            if self.adaptive else _('Miss'))
        self._redraw()

    def _cell_color(self, cell: GridCell) -> Tuple[int, int, int, int]:
        if cell == self.wrong:
            return (220, 64, 64, 255)
        if cell in self.clicked:
            return (46, 170, 92, 255)
        if self.phase == 'show' and cell in self.sequence:
            return (64, 96, 255, 255)
        if state.cfg.BLACK_BACKGROUND:
            return (36, 40, 52, 255)
        return (228, 232, 240, 255)

    def _redraw(self) -> None:
        for shape in self.shapes:
            try:
                shape.delete()
            except Exception:
                pass
        self.shapes = []
        for label in self.cell_labels:
            label.delete()
        self.cell_labels = []
        gap = max(3, int(self.cell * 0.08))
        numbers = {cell: index + 1 for index, cell in enumerate(self.sequence)}
        show_numbers = (self.phase == 'show'
                        or (self.phase == 'result' and self.reveal_answer))
        for row in range(self.grid):
            for col in range(self.grid):
                cell = (row, col)
                x = self.origin_x + col * self.cell + gap
                y = self.origin_y + row * self.cell + gap
                side = self.cell - gap * 2
                rect = pyglet.shapes.Rectangle(
                    x, y, side, side, color=self._cell_color(cell),
                    batch=self.batch)
                self.shapes.append(rect)
                if show_numbers and cell in numbers:
                    label = pyglet.text.Label(
                        str(numbers[cell]),
                        font_size=calc_fontsize(18), weight='bold',
                        color=(255, 255, 255, 255), batch=self.batch,
                        x=x + side / 2, y=y + side / 2,
                        anchor_x='center', anchor_y='center',
                        font_name=FONTLIST)
                    self.cell_labels.append(label)
        self.status.text = _('Length %d — %s') % (self.level, self.message)

    def close(self) -> None:
        if MonkeyLadder.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        MonkeyLadder.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='working_memory')

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'result'):
            self.start_round()
        elif symbol == key.C:
            self.open_options()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        cell = self.cell_at(x, y)
        if cell is not None:
            self.click_cell(cell)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
