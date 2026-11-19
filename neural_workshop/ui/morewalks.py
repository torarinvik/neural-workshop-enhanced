# -*- coding: utf-8 -*-
"""More forgiving walks, on screen: a box to push and pull, a maze with
one-way openings, and an ice floor, each on a seven by seven board with
a row of pips for the steps left.

For the agent boundary: Push and Pull, One-Way Doors and Ice Floor have
four ports: up, down, left, right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import morewalks as model
from ..i18n import _
from .ministeps import StepsTask

#: How much of the room the board takes, on every rung.
SCALE = 0.84


class MoreWalkTask(StepsTask):
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

    def _line(self, ends, thick, colour) -> None:
        self._add(pyglet.shapes.Line(*ends, thickness=thick, color=colour,
                                     batch=self.batch,
                                     group=self.body_group))

    def _draw(self, left, bottom, width, height) -> None:
        if self.walk is None:
            return
        p, data = self.puzzle, self.puzzle.data
        ground, wall, mover, goal = self._colours()
        pip = height * 0.05
        x, y, size, _h = self._board(left, bottom + pip * 1.6, width,
                                     height - pip * 1.6)
        side = data['side']
        cell = self._grid(x, y, size, side, ground, wall)
        thick = max(2.0, cell * 0.08)
        if p.kind == 'oneway':
            self._walls(x, y, cell, side, thick, wall)
        else:
            for k in range(1, side):
                for ends in ((x + k * cell, y, x + k * cell, y + size),
                             (x, y + k * cell, x + size, y + k * cell)):
                    self._line(ends, 1.0, wall)
            for bx, by in data['blocks']:
                self._add(pyglet.shapes.Rectangle(
                    x + bx * cell, y + by * cell, cell, cell, color=wall,
                    batch=self.batch, group=self.body_group))
        self._goal(x, y, cell, data['goal'], goal)
        if p.kind == 'pushpull':
            player, box = self.walk.state
            pad = cell * 0.16
            self._add(pyglet.shapes.Rectangle(
                x + box[0] * cell + pad, y + box[1] * cell + pad,
                cell - 2 * pad, cell - 2 * pad, color=goal,
                batch=self.batch, group=self.text_group))
        else:
            (player,) = self.walk.state
        self._mover(x, y, cell, player, mover)
        limit = p.limit
        gap = min(pip * 1.3, size / max(1, limit))
        px = x + (size - gap * limit) / 2
        for i in range(limit):
            used = i < self.walk.presses
            self._box(px + i * gap + gap * 0.15, bottom, gap * 0.7, pip,
                      None if used else mover, wall, thickness=1.0)

    def _walls(self, x, y, cell, side, thick, wall) -> None:
        data = self.puzzle.data
        for cx in range(side):
            for cy in range(side):
                for dx, dy in ((1, 0), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if nx >= side or ny >= side:
                        continue
                    a, b = (cx, cy), (nx, ny)
                    if frozenset((a, b)) in data['doors']:
                        continue
                    one = (a, b) in data['oneway']
                    two = (b, a) in data['oneway']
                    if one or two:
                        self._wedge(x, y, cell, a if one else b,
                                    b if one else a, wall)
                        continue
                    if dx:
                        ends = (x + nx * cell, y + cy * cell,
                                x + nx * cell, y + (cy + 1) * cell)
                    else:
                        ends = (x + cx * cell, y + ny * cell,
                                x + (cx + 1) * cell, y + ny * cell)
                    self._line(ends, thick, wall)

    def _wedge(self, x, y, cell, src, dst, colour) -> None:
        """A wedge on the opening from *src* to *dst*, pointing the way
        it may be passed."""
        dx, dy = dst[0] - src[0], dst[1] - src[1]
        mx = x + (src[0] + 0.5 + dx * 0.5) * cell
        my = y + (src[1] + 0.5 + dy * 0.5) * cell
        px, py = -dy, dx
        tip = (mx + dx * cell * 0.18, my + dy * cell * 0.18)
        self._add(pyglet.shapes.Triangle(
            *tip, mx - dx * cell * 0.12 + px * cell * 0.2,
            my - dy * cell * 0.12 + py * cell * 0.2,
            mx - dx * cell * 0.12 - px * cell * 0.2,
            my - dy * cell * 0.12 - py * cell * 0.2, color=colour,
            batch=self.batch, group=self.text_group))


class PushAndPull(MoreWalkTask):
    """Push or pull a box onto a mark."""

    instance: Optional['PushAndPull'] = None
    TITLE = 'Push and Pull'
    TASK_ID = 'push_and_pull'
    PREFIX = 'PUSHANDPULL'
    KIND = 'pushpull'


class OneWayDoors(MoreWalkTask):
    """A maze with openings that go one way only."""

    instance: Optional['OneWayDoors'] = None
    TITLE = 'One-Way Doors'
    TASK_ID = 'one_way_doors'
    PREFIX = 'ONEWAYDOORS'
    KIND = 'oneway'


class IceFloor(MoreWalkTask):
    """Slide across ice to a stop on the goal."""

    instance: Optional['IceFloor'] = None
    TITLE = 'Ice Floor'
    TASK_ID = 'ice_floor'
    PREFIX = 'ICEFLOOR'
    KIND = 'ice'
