# -*- coding: utf-8 -*-
"""The Sokoban screen: arrows push, U undoes, R restarts.

The thinking lives in :mod:`neural_workshop.sokoban`; this module is
the room drawn on screen and the keys that walk it. Two decisions
matter here:

* Undo is a first-class key, not a mercy. Sokoban's difficulty is
  irreversibility — one wrong push against a wall is forever — and
  the game is about *seeing* that before it happens. Undo lets a
  player explore lines the way a chess player takes moves back in
  analysis; the push count still tells the truth about the final
  line, and the score is the push count.

* The par line says "minimum" only when the solver certified one.
  Levels past the solver's budget are honest about it: the score
  reads "par ≤ N" from the generator's own walk, never pretending a
  bound is a minimum.

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
from ..sokoban import GRADES, Level, generate
from . import cursor, taskoptions
from ..i18n import _

#: Okabe-Ito again, consistent with the rest of the workshop.
WALL = (110, 110, 110)
GOAL = (230, 159, 0)
BOX = (86, 180, 233)
BOX_HOME = (0, 158, 115)
PLAYER = (213, 94, 0)

#: How close to par a solve must be for an adaptive run to climb.
CLIMB_AT = 1.4


class SokobanTask:
    """Push every box onto a goal. Esc returns to the hub."""

    instance: Optional['SokobanTask'] = None

    def __init__(self) -> None:
        if SokobanTask.instance is not None:
            SokobanTask.instance.close()
        self.rng = random.Random()
        self.level: Optional[Level] = None
        self.boxes: frozenset = frozenset()
        self.player = 0
        self.pushes = 0
        self.moves = 0
        self.history: List[Tuple[frozenset, int, int]] = []
        self.trial = 0
        self.results: List[Tuple[int, int, int, bool]] = []
        #                 (rung, pushes, par, certified)
        self.started_at = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        SokobanTask.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SOKOBAN)
        self.start_rung = int(opts['SOKOBAN_LEVEL'])
        self.total_trials = int(opts['SOKOBAN_TRIALS'])
        self.adaptive = bool(opts['SOKOBAN_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('sokoban', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Sokoban'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     arrows: push'
              '     U: undo     R: restart     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _canvas(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(100)
        bottom = from_bottom_edge(56)
        return (window.width * 0.08, bottom,
                window.width * 0.84, max(40.0, top - bottom))

    def _cell_rect(self, cell: int) -> Tuple[float, float, float]:
        """Left, bottom and side of one cell's square on screen."""
        left, bottom, width, height = self._canvas()
        side = min(width / self.level.width, height / self.level.height)
        board_w = side * self.level.width
        board_h = side * self.level.height
        offset_x = left + (width - board_w) / 2
        offset_y = bottom + (height - board_h) / 2
        x = cell % self.level.width
        y = cell // self.level.width
        return (offset_x + x * side,
                offset_y + (self.level.height - 1 - y) * side, side)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.level = None
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
        self.level = generate(self.rung,
                              seed=self.rng.randrange(1 << 30))
        self.boxes = self.level.boxes
        self.player = self.level.player
        self.pushes = 0
        self.moves = 0
        self.history = []
        self.started_at = time.time()
        self.phase = 'pushing'
        grade = GRADES[self.rung - 1]
        if self.level.minimum is not None:
            self.message = _('%s — minimum %d pushes') % (
                _(grade.name), self.level.minimum)
        else:
            # Too hard to solve exactly, but not unmeasured: the
            # solver proved the lower bound before its budget died.
            self.message = _('%s — between %d and %d pushes') % (
                _(grade.name), self.level.at_least, self.level.bound)
        self._redraw()

    def par(self) -> int:
        """What a solve is judged against: the exact minimum, or the
        proven lower bound. Never the walk's upper bound — on the
        big warrens it runs far past any decent solution, and a par
        nobody should match is not a par."""
        if self.level.minimum is not None:
            return self.level.minimum
        return self.level.at_least

    # --- moving ----------------------------------------------------------

    def step(self, dx: int, dy: int) -> None:
        """One key: walk, or push when a box is in the way."""
        if self.phase != 'pushing':
            return
        level = self.level
        stride = dy * level.width + dx
        ahead = self.player + stride
        if ahead in level.walls:
            return
        if ahead in self.boxes:
            beyond = ahead + stride
            if beyond in level.walls or beyond in self.boxes:
                return
            self.history.append((self.boxes, self.player, self.pushes))
            self.boxes = (self.boxes - {ahead}) | {beyond}
            self.pushes += 1
        else:
            self.history.append((self.boxes, self.player, self.pushes))
        self.player = ahead
        self.moves += 1
        if self.boxes <= level.goals:
            self._solved()
        self._redraw()

    def undo(self) -> None:
        if self.phase != 'pushing' or not self.history:
            return
        self.boxes, self.player, self.pushes = self.history.pop()
        self.moves = max(0, self.moves - 1)
        self._redraw()

    def restart(self) -> None:
        if self.phase != 'pushing':
            return
        self.boxes = self.level.boxes
        self.player = self.level.player
        self.pushes = 0
        self.moves = 0
        self.history = []
        self._redraw()

    def _solved(self) -> None:
        certified = self.level.minimum is not None
        par = self.par()
        self.results.append((self.rung, self.pushes, par, certified))
        took = int(time.time() - self.started_at)
        if certified and self.pushes <= par:
            self.message = _('Perfect — the minimum %d pushes, %ds') % (
                par, took)
        elif certified:
            self.message = _('Solved in %d pushes — minimum was %d') % (
                self.pushes, par)
        else:
            self.message = _('Solved in %d pushes — provably at '
                             'least %d') % (self.pushes, par)
        if self.adaptive:
            if self.pushes <= par * CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif self.pushes > par * 2:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'solved'
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d puzzles, %d%% push efficiency, highest '
                         'rung %d') % (tally['solved'],
                                       tally['efficiency'],
                                       tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        pars = sum(par for _r, _p, par, _c in self.results)
        pushed = sum(pushes for _r, pushes, _p, _c in self.results)
        return {
            'solved': len(self.results),
            'efficiency': int(round(100. * pars / pushed)) if pushed else 0,
            'best_rung': max((rung for rung, _p, _par, _c in self.results),
                             default=0),
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
        if self.level is not None and self.phase in ('pushing', 'solved'):
            level = self.level
            for cell in range(level.width * level.height):
                x, y, side = self._cell_rect(cell)
                pad = side * 0.04
                if cell in level.walls:
                    self.drawn.append(pyglet.shapes.Rectangle(
                        x + pad, y + pad, side - 2 * pad, side - 2 * pad,
                        color=WALL, batch=self.batch))
                elif cell in level.goals and cell not in self.boxes:
                    self.drawn.append(pyglet.shapes.Circle(
                        x + side / 2, y + side / 2, side * 0.13,
                        color=GOAL, batch=self.batch))
            for box in self.boxes:
                x, y, side = self._cell_rect(box)
                pad = side * 0.16
                self.drawn.append(pyglet.shapes.Rectangle(
                    x + pad, y + pad, side - 2 * pad, side - 2 * pad,
                    color=BOX_HOME if box in self.level.goals else BOX,
                    batch=self.batch))
            x, y, side = self._cell_rect(self.player)
            self.drawn.append(pyglet.shapes.Circle(
                x + side / 2, y + side / 2, side * 0.3,
                color=PLAYER, batch=self.batch))
        self._update_status()

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase in ('pushing', 'solved'):
            parts.append(_('puzzle %d/%d   pushes %d')
                         % (self.trial, self.total_trials, self.pushes))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if SokobanTask.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        SokobanTask.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='planning')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'solved':
                self._next_trial()
        elif symbol in (key.UP, key.W):
            self.step(0, -1)
        elif symbol in (key.DOWN, key.S):
            self.step(0, 1)
        elif symbol in (key.LEFT, key.A):
            self.step(-1, 0)
        elif symbol in (key.RIGHT, key.D):
            self.step(1, 0)
        elif symbol == key.U:
            self.undo()
        elif symbol == key.R:
            self.restart()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
