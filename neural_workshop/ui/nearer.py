# -*- coding: utf-8 -*-
"""Which Is Nearer? on screen: a window onto the scene, buttons below.

Each solid carries its number just above it, in type of one size, so
the number says nothing about distance; click the solid or its button,
or press the number. From rung 20 click them all, nearest first: each
right one is marked with its place, and the first wrong one ends it.

For the agent boundary: ports 0-5 choose solids 1-6, counted left to
right across the page at the middle of a sway.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

from .. import nearer as model, space
from ..geometry import calc_fontsize
from ..i18n import _
from . import spacepaint
from .spacetask import RIGHT, WRONG, ChoiceTask

SKY = (232, 236, 242)
SKY_DARK = (30, 34, 42)


class WhichIsNearer(ChoiceTask):
    """Click the nearest solid; later, all of them nearest first."""

    instance: Optional['WhichIsNearer'] = None

    TITLE = 'Which Is Nearer?'
    TASK_ID = 'which_is_nearer'
    PREFIX = 'WHICH_IS_NEARER'
    CATEGORY = 'perception'
    FEEDBACK = 3.0

    def __init__(self) -> None:
        self.picked: List[int] = []
        super().__init__()

    def _make(self):
        self.picked = []
        return model.deal(self.rung, rng=self.rng)

    def _clear_trial(self) -> None:
        super()._clear_trial()
        self.picked = []

    def _now(self) -> float:
        return self.clock() - self.started_at

    def choose(self, index: int) -> None:
        puzzle = self.puzzle
        if self.phase != self.PLAY or puzzle is None \
                or not 0 <= index < len(puzzle.solids):
            return
        if not puzzle.ask_order:
            super().choose(index)
            return
        if index in self.picked:
            return
        self.chosen = index
        if index != puzzle.order[len(self.picked)]:
            self._judge(False, _('No: %s is not next -- the order was %s')
                        % (index + 1, ' '.join(str(i + 1)
                                               for i in puzzle.order)))
            return
        self.picked.append(index)
        if len(self.picked) == len(puzzle.solids):
            self._judge(True, _('Right: all %d in order')
                        % len(self.picked))
        else:
            self._redraw()

    def _verdict(self, right: bool) -> str:
        nearest = self.puzzle.answer + 1
        return (_('Right: %d is nearest') if right
                else _('No: %d is nearest')) % nearest

    def _tick(self) -> None:
        if self.puzzle is not None and self.puzzle.cue == 'motion':
            self._redraw()

    def _mark(self, index: int):
        puzzle = self.puzzle
        if puzzle is not None and puzzle.ask_order:
            if index in self.picked:
                return RIGHT, 4
            if self.phase == 'judged' and index == self.chosen:
                return WRONG, 5
            return self.ink, 2
        return super()._mark(index)

    def _draw_buttons(self, left, bottom, width, height) -> None:
        super()._draw_buttons(left, bottom, width, height)
        # A swatch of each solid's colour on its button.
        n = len(self.puzzle.solids)
        for i, solid in enumerate(self.puzzle.solids):
            x, y, w, h, _act = self.hits[len(self.hits) - n + i]
            side = h * 0.5
            self._box(x + h * 0.25, y + h * 0.25, side, side, solid.colour,
                      self.ink, group=self.body_group)

    def _draw_scene(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        t = self._now() if self.phase == self.PLAY else 0.0
        scale = min(width / (2 * model.HALF_W),
                    height / (2 * model.HALF_H))
        cx, cy = left + width / 2, bottom + height / 2
        w, h = 2 * model.HALF_W * scale, 2 * model.HALF_H * scale
        self._box(cx - w / 2, cy - h / 2, w, h,
                  SKY_DARK if self.dark else SKY)
        place = spacepaint.scaled(scale, cx, cy)
        painted = model.scene(puzzle, t)
        spacepaint.paint(self, painted, place, rim_px=1.4)
        size = calc_fontsize(13)
        # Crowded together the numbers would pile up: there the buttons'
        # colours name the solids.
        labelled = [] if puzzle.cue == 'hiding' else model.boxes(painted)
        for tag, (x0, y0, x1, y1) in labelled:
            px, py = place((x0 + x1) / 2, y1)
            words = str(tag + 1)
            if puzzle.ask_order and tag in self.picked:
                words += ' (%d)' % (self.picked.index(tag) + 1)
            border, _thick = self._mark(tag)
            self._text(words, px, py + 4, size, bold=True,
                       anchor_y='bottom', group=self.top_group,
                       colour=border + (255,) if border != self.ink
                       else None)
        # Nearest first, so a click on overlapping solids takes the
        # one in front.
        for tag, (x0, y0, x1, y1) in model.boxes(painted):
            a, b = place(x0, y0)
            c, d = place(x1, y1)
            self.hits.append((a, b, c - a, d - b,
                              lambda i=tag: self.choose(i)))
        if self.phase == 'judged' and puzzle.ask_order:
            self._text(_('nearest first: %s') % ' '.join(
                str(i + 1) for i in puzzle.order), cx, cy - h / 2 + 6,
                calc_fontsize(12), anchor_y='bottom', group=self.top_group)
