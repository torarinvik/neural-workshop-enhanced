# -*- coding: utf-8 -*-
"""Held in mind, on screen: the answer is how the frame showing stands
to one that is no longer showing.

The four panels are up throughout and a question mark joins them when
the question is put; presses before that are ignored.

For the agent boundary: Changed Tile and Swapped Boxes have four ports
each, one a panel, in reading order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Iterator, Optional, Tuple

import pyglet

from .. import inmind as model
from .. import lookback
from .lookback import BackTask


class MindTask(BackTask):
    """Four panels, and a question about them and an earlier frame."""

    def _make(self):
        return model.deal(self.KIND, self.rung, rng=self.rng)

    def _tint(self, hue: int) -> Tuple[int, ...]:
        colour = lookback.HUES[hue]
        return tuple(min(255, c + 70) for c in colour) if self.dark \
            else colour

    def _panels(self, left, bottom, width,
                height) -> Iterator[Tuple[int, float, float, float]]:
        """Each port's panel: the port, its corner and its side."""
        cols, rows = {'row': (4, 1), 'column': (1, 4),
                      'square': (2, 2)}[self.puzzle.data['layout']]
        cell = min(width * 0.8 / cols, height * 0.9 / rows)
        x0 = left + (width - cell * cols) / 2
        y0 = bottom + (height - cell * rows) / 2
        for port in range(model.PLACES):
            x = x0 + (port % cols) * cell
            y = y0 + (rows - 1 - port // cols) * cell
            self._card(port, x + cell * 0.06, y + cell * 0.06, cell * 0.88,
                       cell * 0.88, number=False)
            yield port, x, y, cell
        self._asked(left + width * 0.06, bottom + height / 2, cell * 0.4)

    def _draw_changed(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        f, showing = lookback.frame_at(p, t)
        tiles = p.data['tiles'][p.frames[f]] \
            if showing and p.frames[f] >= 0 else None
        for port, x, y, cell in self._panels(left, bottom, width, height):
            if tiles is not None:
                self.drawn.append(pyglet.shapes.Rectangle(
                    x + cell * 0.2, y + cell * 0.2, cell * 0.6, cell * 0.6,
                    color=self._tint(tiles[port]), batch=self.batch,
                    group=self.text_group))

    def _draw_swapped(self, left, bottom, width, height, t) -> None:
        p, hue = self.puzzle, self._hue()
        f, showing = lookback.frame_at(p, t)
        pair = p.data['pairs'][f - 1] if showing and f else ()
        ends = []
        for port, x, y, cell in self._panels(left, bottom, width, height):
            if showing and f == 0 and p.frames[0] == port:
                self.drawn.append(pyglet.shapes.Rectangle(
                    x + cell * 0.2, y + cell * 0.2, cell * 0.6, cell * 0.6,
                    color=hue, batch=self.batch, group=self.text_group))
            if port in pair:
                ends.append((x + cell / 2, y + cell / 2, cell))
                self.drawn.append(pyglet.shapes.Circle(
                    x + cell / 2, y + cell / 2, cell * 0.16, color=self.ink,
                    batch=self.batch, group=self.text_group))
        if len(ends) == 2:
            (x1, y1, cell), (x2, y2, _cell) = ends
            self.drawn.append(pyglet.shapes.Line(
                x1, y1, x2, y2, thickness=cell * 0.07, color=self.ink,
                batch=self.batch, group=self.text_group))


class ChangedTile(MindTask):
    """Four tiles show twice: which one changed its hue?"""
    instance: Optional['ChangedTile'] = None
    TITLE, TASK_ID, PREFIX = 'Changed Tile', 'changed_tile', 'CHANGEDTILE'
    KIND = 'changed'


class SwappedBoxes(MindTask):
    """A box lights, then pairs change places: where is the light?"""
    instance: Optional['SwappedBoxes'] = None
    TITLE, TASK_ID, PREFIX = ('Swapped Boxes', 'swapped_boxes',
                              'SWAPPEDBOXES')
    KIND = 'swapped'
