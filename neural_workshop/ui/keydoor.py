# -*- coding: utf-8 -*-
"""Key and Door.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import keydoor as model
from .longwalk import SCALE, LongWalkTask

KEY = (200, 150, 20)


class KeyAndDoor(LongWalkTask):
    """Key and Door."""

    instance: Optional['KeyAndDoor'] = None
    TITLE = 'Key and Door'
    TASK_ID = 'key_and_door'
    PREFIX = 'KEYANDDOOR'
    KIND = model.KIND

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.rung, rng=self.rng)
        self.walk = model.Walk(self.puzzle)
        self.place = (self.rng.random(), self.rng.random(), SCALE)
        self.message = self.puzzle.question
        return True

    def _marks(self, x, y, cell, goal, mover) -> None:
        data = self.puzzle.data
        here, held = self.walk.state
        gx, gy = data['goal']
        if not held:
            pad = cell * 0.18
            self._add(pyglet.shapes.Rectangle(
                x + gx * cell + pad, y + gy * cell + pad, cell - 2 * pad,
                cell - 2 * pad, color=goal, batch=self.batch,
                group=self.body_group))
        else:
            self._goal(x, y, cell, data['goal'], goal)
        if not held:
            kx, ky = data['key']
            self._add(pyglet.shapes.Star(
                x + (kx + 0.5) * cell, y + (ky + 0.5) * cell, cell * 0.3,
                cell * 0.14, 5, color=KEY, batch=self.batch,
                group=self.text_group))
        self._mover(x, y, cell, here, mover)
        if held:
            self._add(pyglet.shapes.Star(
                x + (here[0] + 0.5) * cell, y + (here[1] + 0.5) * cell,
                cell * 0.13, cell * 0.06, 5, color=KEY, batch=self.batch,
                group=self.top_group))
