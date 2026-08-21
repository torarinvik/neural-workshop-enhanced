# -*- coding: utf-8 -*-
"""The Maze screen: arrows walk, R restarts.

The thinking lives in :mod:`neural_workshop.maze`; this module is the
maze drawn on screen and the keys that walk it. Two decisions matter
here:

* There is no undo, and its absence is the point. Sokoban has one
  because a push is irreversible and the game is about seeing that
  coming; nothing in a maze is irreversible, so an undo key would
  only be a way of un-spending steps — and steps are the whole score.
  Walking back costs what walking back costs. ``R`` restarts the maze
  from the beginning if a line turns out to be wrong, and the count
  starts again with it.

* The par is always a real minimum. The solver here is exact at every
  size the ladder offers, so unlike Sokoban this screen never has to
  say "at most" — a maze is walked against the number of steps it
  actually takes, and a perfect walk is a perfect walk.

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
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..maze import GRADES, Maze, generate
from . import cursor, taskoptions
from .verdict import VerdictLabel
from ..i18n import _

#: Okabe-Ito, as everywhere else in the workshop. Six door colours,
#: which is what the palette can keep apart at a glance and so what
#: the ladder is allowed to ask for; the walker takes the seventh so
#: it is never mistaken for a key.
WALL = (110, 110, 110)
KEY_COLORS: Tuple[Tuple[int, int, int], ...] = (
    (230, 159, 0),      # orange
    (86, 180, 233),     # sky blue
    (0, 158, 115),      # green
    (240, 228, 66),     # yellow
    (0, 114, 178),      # blue
    (213, 94, 0),       # vermilion
)
WALKER = (204, 121, 167)                 # reddish purple

#: Keys and locked doors carry a thin rim in the ink colour. Two of
#: the six — the yellow especially — are nearly invisible against a
#: white background on their own, and a rim fixes all six at once
#: rather than swapping colours the rest of the workshop already uses.

#: How close to par a walk must be for an adaptive run to climb. A
#: quarter over the minimum is a walk that got the order right and
#: wasted a corridor or two, which is what a rung should reward.
CLIMB_AT = 1.25


class MazeTask:
    """Find the keys, open the doors, get out. Esc returns to the hub."""

    instance: Optional['MazeTask'] = None

    def __init__(self) -> None:
        if MazeTask.instance is not None:
            MazeTask.instance.close()
        self.rng = random.Random()
        self.maze: Optional[Maze] = None
        self.walker = 0
        self.held = 0
        self.steps = 0
        self.walked: Set[int] = set()
        self.trial = 0
        self.results: List[Tuple[int, int, int]] = []   # (rung, steps, par)
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
        MazeTask.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.MAZE)
        self.start_rung = int(opts['MAZE_LEVEL'])
        self.total_trials = int(opts['MAZE_TRIALS'])
        self.adaptive = bool(opts['MAZE_ADAPTIVE'])
        self.show_trail = bool(opts['MAZE_SHOW_TRAIL'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('maze', on_apply=self.apply_options)

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
            _('Maze'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     arrows: walk'
              '     R: restart     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour; tests/check_band.py is what says nothing else
        # this task draws puts a saturated colour in the bottom quarter.
        # Rebuilt with the chrome, so a verdict already up is put back —
        # a relayout on the frame a trial settles would otherwise drop
        # it, and an outcome only sometimes derivable is worse than one
        # that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
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
        side = min(width / self.maze.width, height / self.maze.height)
        offset_x = left + (width - side * self.maze.width) / 2
        offset_y = bottom + (height - side * self.maze.height) / 2
        x = cell % self.maze.width
        y = cell // self.maze.width
        return (offset_x + x * side,
                offset_y + (self.maze.height - 1 - y) * side, side)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.maze = None
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
        self.verdict_shown = None
        self.verdict.clear()
        self.maze = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self._restart_walk()
        self.started_at = time.time()
        self.phase = 'walking'
        grade = GRADES[self.rung - 1]
        doors = len(self.maze.doors)
        if doors:
            self.message = _('%s — %d doors, %d steps at best') % (
                _(grade.name), doors, self.maze.minimum)
        else:
            self.message = _('%s — %d steps at best') % (
                _(grade.name), self.maze.minimum)
        self._redraw()

    def par(self) -> int:
        """What a walk is judged against — always an exact minimum."""
        return self.maze.minimum

    def _restart_walk(self) -> None:
        self.walker = self.maze.start
        self.held = 0
        self.steps = 0
        self.walked = {self.maze.start}
        self._take_key()

    # --- walking ---------------------------------------------------------

    def _take_key(self) -> None:
        for colour, cell in enumerate(self.maze.keys):
            if cell == self.walker:
                self.held |= 1 << colour

    def needs_key(self, cell: int) -> Optional[int]:
        """The colour barring *cell*, or None when it is walkable."""
        for colour, door in enumerate(self.maze.doors):
            if door == cell and not self.held >> colour & 1:
                return colour
        return None

    def step(self, dx: int, dy: int) -> None:
        """One key: walk a cell, if there is a cell there to walk to."""
        if self.phase != 'walking':
            return
        maze = self.maze
        x, y = self.walker % maze.width, self.walker // maze.width
        nx, ny = x + dx, y + dy
        if not (0 <= nx < maze.width and 0 <= ny < maze.height):
            return
        ahead = ny * maze.width + nx
        if ahead in maze.walls:
            return
        if self.needs_key(ahead) is not None:
            self.message = _('Locked — that door needs its key')
            self._update_status()
            return
        self.walker = ahead
        self.steps += 1
        self.walked.add(ahead)
        self._take_key()
        if self.walker == maze.way_out:
            self._solved()
        self._redraw()

    def restart(self) -> None:
        if self.phase != 'walking':
            return
        self._restart_walk()
        self.message = _('Back to the start')
        self._redraw()

    def _solved(self) -> None:
        par = self.par()
        self.results.append((self.rung, self.steps, par))
        took = int(time.time() - self.started_at)
        if self.steps <= par:
            self.message = _('Perfect — the minimum %d steps, %ds') % (
                par, took)
        else:
            self.message = _('Out in %d steps — the minimum was %d') % (
                self.steps, par)
        if self.adaptive:
            if self.steps <= par * CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif self.steps > par * 2:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'solved'
        self.verdict_shown = (self.steps <= par, self.message)
        self.verdict.show(*self.verdict_shown)

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d mazes, %d%% step efficiency, highest '
                         'rung %d') % (tally['solved'], tally['efficiency'],
                                       tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        pars = sum(par for _r, _s, par in self.results)
        walked = sum(steps for _r, steps, _p in self.results)
        return {
            'solved': len(self.results),
            'efficiency': int(round(100. * pars / walked)) if walked else 0,
            'best_rung': max((rung for rung, _s, _p in self.results),
                             default=0),
            'perfect': sum(1 for _r, steps, par in self.results
                           if steps <= par),
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
        if self.maze is not None and self.phase in ('walking', 'solved'):
            self._draw_maze()
        self._update_status()

    def _draw_maze(self) -> None:
        maze = self.maze
        for cell in maze.walls:
            x, y, side = self._cell_rect(cell)
            self.drawn.append(pyglet.shapes.Rectangle(
                x, y, side + 1, side + 1, color=WALL, batch=self.batch))
        if self.show_trail:
            for cell in self.walked:
                x, y, side = self._cell_rect(cell)
                self.drawn.append(pyglet.shapes.Rectangle(
                    x + side * 0.38, y + side * 0.38, side * 0.24,
                    side * 0.24, color=self.ink + (70,), batch=self.batch))
        # The way out: a frame rather than a fill, so it reads as a
        # doorway and never as one more coloured thing to collect.
        x, y, side = self._cell_rect(maze.way_out)
        self.drawn.append(pyglet.shapes.BorderedRectangle(
            x + side * 0.1, y + side * 0.1, side * 0.8, side * 0.8,
            border=max(2.0, side * 0.14), color=self.background,
            border_color=self.ink, batch=self.batch))
        for colour, cell in enumerate(maze.doors):
            x, y, side = self._cell_rect(cell)
            shade = KEY_COLORS[colour % len(KEY_COLORS)]
            if self.held >> colour & 1:
                # Opened: the frame stays so the route is still legible.
                self.drawn.append(pyglet.shapes.BorderedRectangle(
                    x, y, side + 1, side + 1, border=max(1.5, side * 0.1),
                    color=self.background, border_color=shade,
                    batch=self.batch))
            else:
                self.drawn.append(pyglet.shapes.BorderedRectangle(
                    x, y, side + 1, side + 1, border=max(1.0, side * 0.07),
                    color=shade, border_color=self.ink, batch=self.batch))
        for colour, cell in enumerate(maze.keys):
            if self.held >> colour & 1:
                continue
            x, y, side = self._cell_rect(cell)
            shade = KEY_COLORS[colour % len(KEY_COLORS)]
            self.drawn.append(pyglet.shapes.Circle(
                x + side / 2, y + side / 2, side * 0.34, color=self.ink,
                batch=self.batch))
            self.drawn.append(pyglet.shapes.Circle(
                x + side / 2, y + side / 2, side * 0.28, color=shade,
                batch=self.batch))
            self.drawn.append(pyglet.shapes.Circle(
                x + side / 2, y + side / 2, side * 0.12,
                color=self.background, batch=self.batch))
        x, y, side = self._cell_rect(self.walker)
        self.drawn.append(pyglet.shapes.Circle(
            x + side / 2, y + side / 2, side * 0.34, color=WALKER,
            batch=self.batch))

    def keys_left(self) -> int:
        """Keys still out there in the maze."""
        return sum(1 for colour in range(len(self.maze.keys))
                   if not self.held >> colour & 1)

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase in ('walking', 'solved') and self.maze is not None:
            parts.append(_('maze %d/%d   steps %d')
                         % (self.trial, self.total_trials, self.steps))
            left = self.keys_left()
            if left:
                parts.append(_('%d keys to find') % left if left > 1
                             else _('one key to find'))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if MazeTask.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        MazeTask.instance = None

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
