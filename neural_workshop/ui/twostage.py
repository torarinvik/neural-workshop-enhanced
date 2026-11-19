# -*- coding: utf-8 -*-
"""Forgiving walks in two stages, on screen: an open floor with blocks,
a row of pips for the steps left, and a half-way point.

Fetch and Carry draws a star for the thing, which rides on the player
once picked up, and a hollow square for the mark. Plate and Gate draws
the goal in a pen of blocks, a bar across its opening while the gate is
shut, and a round plate.

For the agent boundary: Fetch and Carry and Plate and Gate have four
ports: up, down, left, right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import twostage as model
from .longwalk import SCALE, LongWalkTask

THING = (200, 150, 20)
PLATE = (90, 150, 60)


class TwoStageTask(LongWalkTask):
    """A walk with a half-way point to reach first."""

    def _make(self):
        return model.deal(self.KIND, self.rung, rng=self.rng)

    def _deal(self) -> bool:
        self.puzzle = self._make()
        self.walk = model.Walk(self.puzzle)
        self.place = (self.rng.random(), self.rng.random(), SCALE)
        self.message = self.puzzle.question
        return True

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
        for k in range(1, side):
            for ends in ((x + k * cell, y, x + k * cell, y + size),
                         (x, y + k * cell, x + size, y + k * cell)):
                self._add(pyglet.shapes.Line(
                    *ends, thickness=1.0, color=wall, batch=self.batch,
                    group=self.body_group))
        for bx, by in data['blocks']:
            self._add(pyglet.shapes.Rectangle(
                x + bx * cell, y + by * cell, cell, cell, color=wall,
                batch=self.batch, group=self.body_group))
        here, stage = self.walk.state
        if self.puzzle.kind == 'fetch':
            self._goal(x, y, cell, data['mark'], goal)
            at = here if stage else data['thing']
            r = cell * (0.14 if stage else 0.3)
            self._add(pyglet.shapes.Star(
                x + (at[0] + 0.5) * cell, y + (at[1] + 0.5) * cell, r,
                r * 0.45, 5, color=THING, batch=self.batch,
                group=self.top_group))
        else:
            gx, gy = data['goal']
            self._add(pyglet.shapes.Circle(
                x + (gx + 0.5) * cell, y + (gy + 0.5) * cell, cell * 0.3,
                color=goal, batch=self.batch, group=self.body_group))
            px, py = data['plate']
            self._add(pyglet.shapes.Arc(
                x + (px + 0.5) * cell, y + (py + 0.5) * cell, cell * 0.32,
                segments=40, thickness=max(2.0, cell * 0.08),
                color=PLATE, batch=self.batch, group=self.body_group))
            if not stage:
                ex, ey = data['gate']
                mx, my = (gx + ex + 1) / 2, (gy + ey + 1) / 2
                half = cell * 0.45
                if ex != gx:
                    ends = (x + mx * cell, y + my * cell - half,
                            x + mx * cell, y + my * cell + half)
                else:
                    ends = (x + mx * cell - half, y + my * cell,
                            x + mx * cell + half, y + my * cell)
                self._add(pyglet.shapes.Line(
                    *ends, thickness=max(3.0, cell * 0.14), color=wall,
                    batch=self.batch, group=self.top_group))
        self._mover(x, y, cell, here, mover)
        limit = self.puzzle.limit
        gap = min(pip * 1.3, size / max(1, limit))
        px0 = x + (size - gap * limit) / 2
        for i in range(limit):
            used = i < self.walk.presses
            self._box(px0 + i * gap + gap * 0.15, bottom, gap * 0.7, pip,
                      None if used else mover, wall, thickness=1.0)


class FetchAndCarry(TwoStageTask):
    """Walk to a thing, then carry it to a mark."""

    instance: Optional['FetchAndCarry'] = None
    TITLE = 'Fetch and Carry'
    TASK_ID = 'fetch_and_carry'
    PREFIX = 'FETCHANDCARRY'
    KIND = 'fetch'


class PlateAndGate(TwoStageTask):
    """Step on a plate to open a gate, then through it to the goal."""

    instance: Optional['PlateAndGate'] = None
    TITLE = 'Plate and Gate'
    TASK_ID = 'plate_and_gate'
    PREFIX = 'PLATEANDGATE'
    KIND = 'plate'
