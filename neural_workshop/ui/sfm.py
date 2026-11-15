# -*- coding: utf-8 -*-
"""Shape from Motion on screen: a field of moving dots, answers below.

The dots are made once a trial and moved every frame rather than drawn
afresh, since there are up to three hundred of them. After the verdict
they stop where they are.

For the agent boundary: ports 0-5 choose answers 1-6.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

import pyglet

from .. import sfm as model
from ..geometry import calc_fontsize
from ..i18n import _
from .spacetask import ChoiceTask

FIELD = (16, 18, 24)
DOT = (236, 238, 242)


class ShapeFromMotion(ChoiceTask):
    """Name the solid a turning cloud of dots lies on."""

    instance: Optional['ShapeFromMotion'] = None

    TITLE = 'Shape from Motion'
    TASK_ID = 'shape_from_motion'
    PREFIX = 'SHAPE_FROM_MOTION'
    CATEGORY = 'perception'

    def __init__(self) -> None:
        self.dot_shapes: List[pyglet.shapes.Rectangle] = []
        self.field = (0.0, 0.0, 1.0)
        super().__init__()

    def _make(self):
        self._drop_dots()
        return model.deal(self.rung, rng=self.rng)

    def _clear_trial(self) -> None:
        super()._clear_trial()
        self._drop_dots()

    def _drop_dots(self) -> None:
        for shape in getattr(self, 'dot_shapes', []):
            shape.delete()
        self.dot_shapes = []

    def _verdict(self, right: bool) -> str:
        puzzle = self.puzzle
        if puzzle.kind == 'spin':
            return super()._verdict(right)
        truth = model.NAMES[puzzle.solid]
        return (_('Right: a %s') if right else _('No: a %s')) % \
            truth.lower()

    def _draw_scene(self, left, bottom, width, height) -> None:
        side = min(width, height)
        x0 = left + (width - side * 1.2) / 2
        self._box(x0, bottom, side * 1.2, side, FIELD)
        self.field = (left + width / 2, bottom + side / 2,
                      side / 2 / model.VIEW)
        if self.phase == 'judged':
            self._text(model.NAMES[self.puzzle.solid] if
                       self.puzzle.kind == 'shape' else
                       self.puzzle.choices[self.puzzle.answer],
                       left + width / 2, bottom + 6, calc_fontsize(12),
                       colour=DOT + (255,), anchor_y='bottom',
                       group=self.top_group)
        self._place_dots()

    def _place_dots(self) -> None:
        puzzle = self.puzzle
        if puzzle is None:
            return
        t = self.clock() - self.started_at
        points = model.dots(puzzle, t)
        cx, cy, scale = self.field
        px = max(2.0, scale * 0.028)
        # A relayout builds a new batch; dots left in the old one would
        # never be drawn.
        if getattr(self, 'dot_batch', None) is not self.batch:
            self._drop_dots()
            self.dot_batch = self.batch
        while len(self.dot_shapes) < len(points):
            self.dot_shapes.append(pyglet.shapes.Rectangle(
                0, 0, px, px, color=DOT, batch=self.batch,
                group=self.top_group))
        for shape, (x, y, size) in zip(self.dot_shapes, points):
            d = px * size
            shape.x = cx + x * scale - d / 2
            shape.y = cy + y * scale - d / 2
            shape.width = shape.height = d

    def _tick(self) -> None:
        self._place_dots()
