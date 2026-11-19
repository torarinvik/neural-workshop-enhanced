# -*- coding: utf-8 -*-
"""Cues kept over a wait, on screen: four places, a cue that lights in
one of them, and the question.

Look 0 draws four squares in a row, a column or a square, the ports in
reading order; look 1 four beads round a ring, top, right, bottom and
left, the ports the other way round. A cue fills its place in its
colour for the frame it shows; a job's dot is small and dark, and goes
out once pressed. The question frame adds a question mark and, where a
task asks for one cue of several, that cue's colour beside it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import framed, keptcue
from ..i18n import _
from .framed import FrameTask


class CueTask(FrameTask):
    """A trial of a family built on :mod:`neural_workshop.keptcue`."""

    FOOTNOTE = _('watch, keep your hands off until the question mark, '
                 'then click a place or press its number   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.run = keptcue.Run(self.puzzle)
        return ok

    def _spots(self, left, bottom, width, height):
        """Each place's corner, by place, and the places' side."""
        data = self.puzzle.data
        if data['look'] == 0:
            cols, rows = {'row': (4, 1), 'column': (1, 4),
                          'square': (2, 2)}[data['layout']]
            cell = min(width * 0.7 / cols, height * 0.86 / rows)
            x0, y0 = self._placed(left + width * 0.12, bottom,
                                  width * 0.88, height, cell * cols,
                                  cell * rows)
            return [(x0 + (i % cols) * cell,
                     y0 + (rows - 1 - i // cols) * cell)
                    for i in range(keptcue.PLACES)], cell
        cell = min(width, height) * 0.24
        r = min(width, height) * 0.3
        cx, cy = self._placed(left + width * 0.12, bottom, width * 0.88,
                              height, 2 * r + cell, 2 * r + cell)
        cx, cy = cx + r + cell / 2, cy + r + cell / 2
        pts = [(cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy)]
        return [(x - cell / 2, y - cell / 2) for x, y in pts], cell

    def _colour(self, colour: int):
        return keptcue.COLOURS[self.puzzle.data['look']][colour]

    def _fill(self, x, y, cell, colour) -> None:
        if self.puzzle.data['look'] == 0:
            self.drawn.append(pyglet.shapes.Rectangle(
                x + cell * 0.2, y + cell * 0.2, cell * 0.6, cell * 0.6,
                color=colour, batch=self.batch, group=self.text_group))
        else:
            self.drawn.append(pyglet.shapes.Circle(
                x + cell / 2, y + cell / 2, cell * 0.3, color=colour,
                batch=self.batch, group=self.text_group))

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p, data = self.puzzle, self.puzzle.data
        look = data['look']
        spots, cell = self._spots(left, bottom, width, height)
        order = keptcue.order(look)
        rim = framed.RIMS[data['rim']]
        for port in range(keptcue.PLACES):
            x, y = spots[order[port]]
            self._card(port, x + cell * 0.06, y + cell * 0.06, cell * 0.88,
                       cell * 0.88, number=False)
            if look == 1:
                self.drawn.append(pyglet.shapes.Arc(
                    x + cell / 2, y + cell / 2, cell * 0.36, segments=40,
                    thickness=2.0, color=rim, batch=self.batch,
                    group=self.body_group))
        f, showing = framed.frame_at(p, t)
        for frame, place, colour in data['cues']:
            if frame == f and showing:
                x, y = spots[place]
                self._fill(x, y, cell, self._colour(colour))
        run = self.run
        if run is not None and not run.open:
            j = run.job()
            if j is not None and j not in run.done:
                x, y = spots[data['jobs'][j][1]]
                self.drawn.append(pyglet.shapes.Circle(
                    x + cell / 2, y + cell / 2, cell * 0.09,
                    color=self.ink, batch=self.batch,
                    group=self.top_group))
        size = min(cell * 0.4, width * 0.05)
        self._asked(left + width * 0.05, bottom + height * 0.6, size)
        if run is not None and run.open and data.get('asked') is not None:
            x, y = left + width * 0.05 - size, bottom + height * 0.3
            self._fill(x, y, size * 2, self._colour(data['asked']))
