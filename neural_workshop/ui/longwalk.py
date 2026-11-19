# -*- coding: utf-8 -*-
"""Forgiving walks, on screen: a seven by seven maze, a goal, and a row
of pips for the steps allowed.

A press into a wall or down a dead end uses a step and the trial goes
on; it ends at the goal or when the last step is used. The board keeps
its size on every rung and moves a little from trial to trial.

For the agent boundary: Long Way Round has four ports: up, down,
left, right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import longwalk as model
from ..i18n import _
from .ministeps import StepsTask

#: How much of the room the board takes, on every rung.
SCALE = 0.84


class LongWalkTask(StepsTask):
    """A walk where a wrong press wastes a step."""

    FOOTNOTE = _('arrow keys: move   the pips are the steps left   '
                 'Esc: menu')

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.KIND, self.rung, rng=self.rng)
        self.walk = model.Walk(self.puzzle)
        self.place = (self.rng.random(), self.rng.random(), SCALE)
        self.message = self.puzzle.question
        return True

    def steer(self, port: int) -> None:
        walk = self.walk
        if self.phase != self.PLAY or walk is None:
            return
        if walk.press(port) is None:
            return
        if walk.result is not None:
            self._judge(*walk.result)
            return
        self._redraw()

    def _facts(self) -> str:
        if self.walk is None:
            return ''
        return _('rung %d   %d/%d   %d steps left') % (
            self.rung, self.trial, self.total_trials, self.walk.left())

    def _draw(self, left, bottom, width, height) -> None:
        if self.walk is None:
            return
        data = self.puzzle.data
        ground, wall, mover, goal = self._colours()
        pip = height * 0.05
        x, y, size, _h = self._board(left, bottom + pip * 1.6, width,
                                     height - pip * 1.6)
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
        self._marks(x, y, cell, goal, mover)
        # The steps left, as pips under the board.
        limit = self.puzzle.limit
        gap = min(pip * 1.3, size / max(1, limit))
        px = x + (size - gap * limit) / 2
        for i in range(limit):
            used = i < self.walk.presses
            self._box(px + i * gap + gap * 0.15, bottom, gap * 0.7, pip,
                      None if used else mover, wall, thickness=1.0)

    def _marks(self, x, y, cell, goal, mover) -> None:
        """The goal and the player, over the walls."""
        self._goal(x, y, cell, self.puzzle.data['goal'], goal)
        self._mover(x, y, cell, self.walk.state[0], mover)


class LongWayRound(LongWalkTask):
    """A maze walk where a wrong press wastes a step."""

    instance: Optional['LongWayRound'] = None
    TITLE = 'Long Way Round'
    TASK_ID = 'long_way_round'
    PREFIX = 'LONGWAYROUND'
    KIND = 'walk'

