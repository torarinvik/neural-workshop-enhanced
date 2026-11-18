# -*- coding: utf-8 -*-
"""The short walks on screen: a maze, a tower, a board of tiles, a
box-pushing room and an open grid, each a few presses from done.

One screen draws all of them; a subclass says which kind it deals.
Arrow keys steer the ones that are steered, number keys press the
tower's six moves and the tiles, and a tile can be clicked.

For the agent boundary: the steered kinds have four ports, up, down,
left and right; the tower has six, peg to peg in the order 1-2, 1-3,
2-1, 2-3, 3-1, 3-2; the tiles have one port a tile, counted along the
rows from the top left. A press that does not bring the goal nearer
ends the trial.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional, Tuple

import pyglet
from pyglet.window import key

from .. import ministeps as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

ARROWS = {key.UP: 0, key.DOWN: 1, key.LEFT: 2, key.RIGHT: 3}
DARK_GROUND = (34, 38, 46)


class StepsTask(RungTask):
    """A puzzle a few presses from done; a wrong press ends it."""

    KIND = ''
    CATEGORY = 'first_steps'
    FEEDBACK = 1.2
    FOOTNOTE = _('arrow keys: move   Esc: menu')

    def __init__(self) -> None:
        self.puzzle = None
        self.walk = None
        #: Paint a green "nearer" after each right press. Only the agent
        #: boundary turns this on, and only when it pays by the press.
        self.coach = False
        self.place: Tuple[float, float, float] = (0.5, 0.5, 1.0)
        super().__init__()

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.walk = None

    def _extra(self) -> dict:
        return {}

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.KIND, self.rung, rng=self.rng,
                                 **self._extra())
        self.walk = model.Walk(self.puzzle)
        self.place = (self.rng.random(), self.rng.random(),
                      0.78 + 0.22 * self.rng.random())
        self.message = self.puzzle.question
        return True

    def steer(self, port: int) -> None:
        walk = self.walk
        if self.phase != self.PLAY or walk is None:
            return
        nearer = walk.press(port)
        if nearer is None:
            return
        if walk.result is not None:
            self._judge(*walk.result)
            return
        if self.coach:
            self.verdict_shown = (True, _('Nearer'))
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _key(self, symbol: int, modifiers: int) -> None:
        if self.puzzle is None:
            return
        if self.puzzle.ports == 4 and symbol in ARROWS:
            self.steer(ARROWS[symbol])
        elif self.puzzle.ports != 4 and key._1 <= symbol <= key._9:
            self.steer(symbol - key._1)

    def _facts(self) -> str:
        if self.walk is None:
            return ''
        return _('rung %d   %d/%d   %d to go') % (
            self.rung, self.trial, self.total_trials,
            model.far(self.puzzle, self.walk.state))

    # --- drawing ---------------------------------------------------------

    def _board(self, left, bottom, width, height, aspect: float = 1.0):
        """Where this trial's board sits: it moves and changes size
        from trial to trial."""
        fx, fy, scale = self.place
        h = min(height, width / aspect) * scale
        w = h * aspect
        return (left + (width - w) * fx, bottom + (height - h) * fy, w, h)

    def _colours(self):
        ground, wall, mover, goal = model.LOOKS[self.puzzle.look]
        if self.dark:
            ground = DARK_GROUND
            wall = tuple(min(255, c + 110) for c in wall)
        return ground, wall, mover, goal

    def _add(self, shape) -> None:
        self.drawn.append(shape)

    def _draw(self, left, bottom, width, height) -> None:
        if self.walk is None:
            return
        getattr(self, '_draw_' + self.puzzle.kind)(left, bottom, width,
                                                   height)

    def _grid(self, x, y, size, side, ground, line) -> float:
        cell = size / side
        self._box(x, y, size, size, ground, line, thickness=3.0)
        return cell

    def _draw_maze(self, left, bottom, width, height) -> None:
        p, data = self.puzzle, self.puzzle.data
        ground, wall, mover, goal = self._colours()
        x, y, size, _h = self._board(left, bottom, width, height)
        side = data['side']
        cell = self._grid(x, y, size, side, ground, wall)
        thick = max(2.0, cell * 0.08)
        for cx in range(side):
            for cy in range(side):
                for dx, dy in ((1, 0), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if nx >= side or ny >= side or frozenset(
                            ((cx, cy), (nx, ny))) in data['doors']:
                        continue
                    if dx:
                        ends = (x + nx * cell, y + cy * cell,
                                x + nx * cell, y + (cy + 1) * cell)
                    else:
                        ends = (x + cx * cell, y + ny * cell,
                                x + (cx + 1) * cell, y + ny * cell)
                    self._add(pyglet.shapes.Line(
                        *ends, thickness=thick, color=wall,
                        batch=self.batch, group=self.body_group))
        self._goal(x, y, cell, data['goal'], goal)
        self._mover(x, y, cell, self.walk.state, mover)

    def _goal(self, x, y, cell, at, colour) -> None:
        pad = cell * 0.2
        self._add(pyglet.shapes.Box(
            x + at[0] * cell + pad, y + at[1] * cell + pad,
            cell - 2 * pad, cell - 2 * pad,
            thickness=max(2.0, cell * 0.1), color=colour,
            batch=self.batch, group=self.body_group))

    def _mover(self, x, y, cell, at, colour) -> None:
        self._add(pyglet.shapes.Circle(
            x + (at[0] + 0.5) * cell, y + (at[1] + 0.5) * cell,
            cell * 0.26, color=colour, batch=self.batch,
            group=self.text_group))

    def _draw_walk(self, left, bottom, width, height) -> None:
        data = self.puzzle.data
        ground, wall, mover, goal = self._colours()
        x, y, size, _h = self._board(left, bottom, width, height)
        side = data['side']
        cell = self._grid(x, y, size, side, ground, wall)
        for k in range(1, side):
            for ends in ((x + k * cell, y, x + k * cell, y + size),
                         (x, y + k * cell, x + size, y + k * cell)):
                self._add(pyglet.shapes.Line(
                    *ends, thickness=1.0, color=wall, batch=self.batch,
                    group=self.body_group))
        self._goal(x, y, cell, data['goal'], goal)
        self._mover(x, y, cell, self.walk.state, mover)

    def _draw_push(self, left, bottom, width, height) -> None:
        data = self.puzzle.data
        ground, wall, mover, goal = self._colours()
        x, y, size, _h = self._board(left, bottom, width, height)
        side = data['side']
        cell = self._grid(x, y, size, side, ground, wall)
        for wx, wy in data['walls']:
            self._add(pyglet.shapes.Rectangle(
                x + wx * cell, y + wy * cell, cell, cell, color=wall,
                batch=self.batch, group=self.body_group))
        self._goal(x, y, cell, data['goal'], goal)
        player, box = self.walk.state
        pad = cell * 0.16
        self._add(pyglet.shapes.Rectangle(
            x + box[0] * cell + pad, y + box[1] * cell + pad,
            cell - 2 * pad, cell - 2 * pad, color=goal, batch=self.batch,
            group=self.text_group))
        self._mover(x, y, cell, player, mover)

    def _draw_tower(self, left, bottom, width, height) -> None:
        data = self.puzzle.data
        ground, wall, mover, goal = self._colours()
        x, y, w, h = self._board(left, bottom, width, height, aspect=1.8)
        self._box(x, y, w, h, ground, wall, thickness=3.0)
        discs = data['discs']
        slot = w / 3.0
        base = y + h * 0.12
        tall = h * 0.7
        thick = min(tall / (discs + 1.5), h * 0.14)
        for peg in range(3):
            cx = x + slot * (peg + 0.5)
            marked = peg == data['goal']
            self._add(pyglet.shapes.Rectangle(
                cx - slot * 0.44, base - h * 0.05, slot * 0.88, h * 0.05,
                color=goal if marked else wall, batch=self.batch,
                group=self.body_group))
            self._add(pyglet.shapes.Rectangle(
                cx - slot * 0.03, base, slot * 0.06, tall, color=wall,
                batch=self.batch, group=self.body_group))
            if marked:
                self._add(pyglet.shapes.Triangle(
                    cx, base + tall, cx, base + tall + h * 0.09,
                    cx + slot * 0.16, base + tall + h * 0.045, color=goal,
                    batch=self.batch, group=self.body_group))
            self._text(str(peg + 1), cx, y + h * 0.035,
                       min(calc_fontsize(12), h * 0.05),
                       colour=tuple(wall) + (255,))
            stack = sorted((d for d, at in enumerate(self.walk.state)
                            if at == peg), reverse=True)
            for level, disc in enumerate(stack):
                half = slot * (0.14 + 0.28 * (disc + 1) / discs) / 1.0
                shade = tuple(int(c * (0.65 + 0.35 * disc / max(1, discs - 1)))
                              for c in mover)
                self._add(pyglet.shapes.Rectangle(
                    cx - half, base + level * thick, 2 * half,
                    thick * 0.86, color=shade, batch=self.batch,
                    group=self.text_group))

    def _tile(self, x, y, size, corner, back, mark) -> None:
        self._add(pyglet.shapes.Rectangle(
            x, y, size, size, color=back, batch=self.batch,
            group=self.body_group))
        k = size * 0.62
        ends = {0: (x, y + size, x + k, y + size, x, y + size - k),
                1: (x + size, y + size, x + size - k, y + size,
                    x + size, y + size - k),
                2: (x + size, y, x + size - k, y, x + size, y + k),
                3: (x, y, x + k, y, x, y + k)}[corner]
        self._add(pyglet.shapes.Triangle(
            *ends, color=mark, batch=self.batch, group=self.text_group))

    def _draw_tiles(self, left, bottom, width, height) -> None:
        data = self.puzzle.data
        ground, wall, mover, goal = self._colours()
        cols, rows = data['cols'], data['rows']
        x, y, w, h = self._board(left, bottom, width, height,
                                 aspect=cols / (rows + 1.2))
        self._box(x, y, w, h, ground, wall, thickness=3.0)
        cell = w / cols
        gap = cell * 0.08
        # The pattern: how every tile should sit.
        sample = cell * 0.7
        top = y + h - sample - gap * 2
        self._tile(x + (w - sample) / 2, top, sample, data['home'], wall,
                   goal)
        back = tuple(int(c * 0.86) for c in ground) if not self.dark \
            else (70, 76, 90)
        for k, turn in enumerate(self.walk.state):
            cx = x + (k % cols) * cell + gap
            cy = y + (rows - 1 - k // cols) * cell + gap
            self._tile(cx, cy, cell - 2 * gap, turn, back, mover)
            self.hits.append((cx, cy, cell - 2 * gap, cell - 2 * gap,
                              lambda port=k: self.steer(port)))


class ShortMaze(StepsTask):
    """The way out is a few steps off."""

    instance: Optional['ShortMaze'] = None
    TITLE = 'Short Maze'
    TASK_ID = 'short_maze'
    PREFIX = 'SHORTMAZE'
    KIND = 'maze'


class ShortMazeSteps(StepsTask):
    """Short Maze, with every right step marked for the agent."""

    instance: Optional['ShortMazeSteps'] = None
    TITLE = 'Short Maze, Step by Step'
    TASK_ID = 'short_maze_steps'
    PREFIX = 'SHORTMAZESTEPS'
    KIND = 'maze'

    def __init__(self):
        super().__init__()
        # The wrapper turns this on: each step nearer is then marked green.
        self.coach = False


class ShortTower(StepsTask):
    """A tower a few moves from stacked."""

    instance: Optional['ShortTower'] = None
    TITLE = 'Short Tower'
    TASK_ID = 'short_tower'
    PREFIX = 'SHORTTOWER'
    KIND = 'tower'
    FOOTNOTE = _('1-6: move a disc (1-2, 1-3, 2-1, 2-3, 3-1, 3-2)   '
                 'Esc: menu')


class TurnedTiles(StepsTask):
    """A board with a few tiles turned out of place."""

    instance: Optional['TurnedTiles'] = None
    TITLE = 'Turned Tiles'
    TASK_ID = 'turned_tiles'
    PREFIX = 'TURNEDTILES'
    KIND = 'tiles'
    FOOTNOTE = _('click a turned tile, or press its number   Esc: menu')


class ShortPush(StepsTask):
    """A box a few presses from its mark."""

    instance: Optional['ShortPush'] = None
    TITLE = 'Short Push'
    TASK_ID = 'short_push'
    PREFIX = 'SHORTPUSH'
    KIND = 'push'


class MarkerWalk(StepsTask):
    """Each port moves the marker one way."""

    instance: Optional['MarkerWalk'] = None
    TITLE = 'Marker Walk'
    TASK_ID = 'marker_walk'
    PREFIX = 'MARKERWALK'
    KIND = 'walk'


class MarkerWalkShuffled(StepsTask):
    """Marker Walk, with which port moves which way dealt per run."""

    instance: Optional['MarkerWalkShuffled'] = None
    TITLE = 'Marker Walk, Shuffled'
    TASK_ID = 'marker_walk_shuffled'
    PREFIX = 'MARKERWALKSHUFFLED'
    KIND = 'walk'
    FOOTNOTE = _('arrow keys move the marker, but not the way they point: '
                 'find out which does what   Esc: menu')

    def __init__(self) -> None:
        self.order = (0, 1, 2, 3)
        super().__init__()

    def start_run(self) -> None:
        order = [0, 1, 2, 3]
        self.rng.shuffle(order)
        self.order = tuple(order)
        super().start_run()

    def _extra(self) -> dict:
        return {'order': self.order}
