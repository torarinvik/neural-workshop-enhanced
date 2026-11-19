# -*- coding: utf-8 -*-
"""Walks from memory, on screen: an open board, the player, and the
goals for the first two frames only.

Nothing else is shown: no rung and no count of steps, so that the frame
holds nothing a player could use in place of memory.

For the agent boundary: Gone From View and In That Order have four
ports: up, down, left, right. Presses while the goals show are ignored.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import memwalk as model
from ..framed import FRAME
from ..i18n import _
from .clocked import ClockedTask
from .ministeps import StepsTask

SCALE = 0.84


class MemWalkTask(ClockedTask, StepsTask):
    """A walk to places shown and then hidden."""

    MODEL = model
    LONGEST_TICK = FRAME
    FOOTNOTE = _('watch where to go, then arrow keys: move   Esc: menu')

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.walk = None
        self.run = None
        self._drop()

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.KIND, self.rung, rng=self.rng)
        self.run = model.Run(self.puzzle)
        self.walk = self.run
        self.control = None
        self.last_tick = self.clock()
        self._drop()
        self.place = (self.puzzle.data['place'][0],
                      self.puzzle.data['place'][1], SCALE)
        self.message = self.puzzle.question
        return True

    def _key(self, symbol: int, modifiers: int) -> None:
        StepsTask._key(self, symbol, modifiers)

    def _facts(self) -> str:
        return _('%d/%d') % (self.trial, self.total_trials)

    def _draw(self, left, bottom, width, height) -> None:
        if self.run is None:
            return
        ground, wall, mover, goal = self._colours()
        x, y, size, _h = self._board(left, bottom, width, height)
        side = model.SIDE
        cell = self._grid(x, y, size, side, ground, wall)
        for k in range(1, side):
            for ends in ((x + k * cell, y, x + k * cell, y + size),
                         (x, y + k * cell, x + size, y + k * cell)):
                self._add(pyglet.shapes.Line(
                    *ends, thickness=1.0, color=wall, batch=self.batch,
                    group=self.body_group))
        shown = self.run.showing()
        if shown is not None:
            self._goal(x, y, cell, self.puzzle.goals[shown], goal)
        self._mover(x, y, cell, self.run.state[0], mover)


class GoneFromView(MemWalkTask):
    """The goal shows, hides, and is walked to from memory."""

    instance: Optional['GoneFromView'] = None
    TITLE = 'Gone From View'
    TASK_ID = 'gone_from_view'
    PREFIX = 'GONEFROMVIEW'
    KIND = 'one'


class InThatOrder(MemWalkTask):
    """Two places show in turn, hide, and are visited in that order."""

    instance: Optional['InThatOrder'] = None
    TITLE = 'In That Order'
    TASK_ID = 'in_that_order'
    PREFIX = 'INTHATORDER'
    KIND = 'two'
