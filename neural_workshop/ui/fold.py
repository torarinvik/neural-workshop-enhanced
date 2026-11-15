# -*- coding: utf-8 -*-
"""Fold It on screen: the net, and the cubes to choose among.

Up to rung 3 the net alone, its squares lettered, and lettered buttons
below. After that the net on the left and the cubes on the right, each
in a numbered card: click the cube the net folds into, or press its
number.

For the agent boundary: ports 0-5 choose answers 1-6.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from .. import fold as model, space
from ..geometry import calc_fontsize
from . import spacepaint
from .spacetask import ChoiceTask


class FoldIt(ChoiceTask):
    """Which cube does the flat net fold into?"""

    instance: Optional['FoldIt'] = None

    TITLE = 'Fold It'
    TASK_ID = 'fold_it'
    PREFIX = 'FOLD_IT'
    CATEGORY = 'reasoning'

    def _make(self):
        puzzle = model.deal(self.rung, rng=self.rng)
        self.BUTTONS = 0.13 if puzzle.kind == 'opposite' else 0.0
        return puzzle

    def _draw_net(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        xs = [x for x, _y in puzzle.net]
        ys = [y for _x, y in puzzle.net]
        cols, rows = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        cell = min(width / (cols + 0.4), height / (rows + 0.4))
        x0 = left + (width - cols * cell) / 2 - min(xs) * cell
        y0 = bottom + (height - rows * cell) / 2 - min(ys) * cell
        for k, ((cx, cy), (glyph, colour, quarter)) in enumerate(
                zip(puzzle.net, puzzle.marks)):
            x, y = x0 + cx * cell, y0 + cy * cell
            spacepaint.polygon(self, ((x, y), (x + cell, y),
                                      (x + cell, y + cell), (x, y + cell)),
                               colour, rim_px=max(1.5, cell * 0.02))
            mid = (x + cell / 2, y + cell / 2)
            angle = math.pi / 2 * quarter
            ca, sa = math.cos(angle), math.sin(angle)
            group = spacepaint.layer(self)
            for part in model.GLYPHS[glyph].parts:
                pts = [(mid[0] + 0.36 * cell * (a * ca - b * sa),
                        mid[1] + 0.36 * cell * (a * sa + b * ca))
                       for a, b in part]
                spacepaint.polygon(self, pts, model.INK, rim=None,
                                   group=group)
            if puzzle.kind == 'opposite':
                self._text(model.LETTERS[k], mid[0], mid[1],
                           min(calc_fontsize(22), cell * 0.4), bold=True,
                           colour=model.INK + (255,), group=self.top_group)

    def _draw_scene(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        if puzzle.kind == 'opposite':
            self._draw_net(left, bottom, width, height)
            return
        net_w = width * 0.38
        self._draw_net(left, bottom, net_w, height)
        n = len(puzzle.cubes)
        cols = 2 if n <= 4 else 3
        rows = int(math.ceil(n / float(cols)))
        gap = width * 0.012
        area_x = left + net_w + gap * 2
        area_w = width - net_w - gap * 2
        cw = (area_w - gap * (cols - 1)) / cols
        ch = (height - gap * (rows - 1)) / rows
        side = min(cw, ch)
        cam = model.camera()
        for i, (cube, turn) in enumerate(puzzle.cubes):
            row, col = divmod(i, cols)
            x = area_x + col * (cw + gap) + (cw - side) / 2
            y = bottom + height - (row + 1) * ch - row * gap + (ch - side) / 2
            self._card(i, x, y, side, side)
            painted = space.render(model.cube_faces(dict(cube), turn), cam)
            spacepaint.paint(self, painted,
                             spacepaint.scaled(side * 0.4, x + side / 2,
                                               y + side / 2),
                             rim_px=max(1.5, side * 0.008))
