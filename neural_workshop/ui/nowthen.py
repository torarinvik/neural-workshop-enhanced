# -*- coding: utf-8 -*-
"""Now and earlier, on screen: things show twice; which is different?

For the agent boundary: Which Moved?, Which Is New? and Which Is Gone?
have four ports, one a card, left to right; their twins Moved Bead, New
Bead and Gone Bead have four, one a card, top to bottom. Traded Places
has five, one a place in the row, left to right; its twin Traded Beads
five, one a place on the arc, right to left. Presses before the
question is put are ignored, and the cards are blank until it is.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import pyglet

from .. import framed
from .. import nowthen as model
from .framed import FrameTask


class NowThenTask(FrameTask):
    """Two showings and a question about what differs."""

    FAMILY = model

    def _draw_at(self, left, bottom, width, height, t) -> None:
        if self.KIND == 'traded':
            self._draw_row(left, bottom, width, height, t)
        else:
            self._draw_board(left, bottom, width, height, t)

    # --- a board of things and four cards --------------------------------

    def _draw_board(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        look = p.data['look']
        _f, showing = self._frame(t)
        if look == 0:
            card = min(width * 0.14, height * 0.2)
            side = min(height - card * 1.35, width * 0.62)
            bx, by = self._placed(left, bottom + card * 1.35, width,
                                  height - card * 1.35, side, side)
            x0 = left + (width - card * 4.6) / 2
            places = [(x0 + i * card * 1.2, bottom) for i in range(4)]
        else:
            card = min(height * 0.2, width * 0.13)
            side = min(height * 0.96, width - card * 2.2)
            bx, by = self._placed(left, bottom, width - card * 1.8,
                                  height, side, side)
            x = left + width - card * 1.25
            y0 = bottom + (height - card * 4.6) / 2
            places = [(x, y0 + i * card * 1.2) for i in range(4)]
        self._board(bx, by, side, look)
        if showing is not None and showing >= 0:
            items = p.data['first'] if showing == 0 else p.data['second']
            spots = framed.spots(look)
            for thing, spot in items:
                if look == 1 and spot < 8:
                    spot = (spot + p.data['turn']) % 8
                fx, fy = spots[spot]
                self._thing(thing, bx + fx * side, by + fy * side,
                            side * 0.1)
        order = framed.port_order(look, model.CARDS)
        for port in range(model.CARDS):
            x, y = places[order[port]]
            self._card(port, x, y, card, card)
            if self.run is not None and self.run.open:
                self._thing(model.card_of(p, port), x + card / 2,
                            y + card * 0.45, card * 0.27)
        self._asked(left + width * 0.04, bottom + height * 0.6, card * 0.4)

    def _board(self, x, y, side, look) -> None:
        line = tuple(int(c * 0.5 + 128 * 0.5) for c in self.ink)
        if look == 0:
            self._box(x, y, side, side, None, line, thickness=1.5)
            for k in (1, 2):
                for ends in ((x + k * side / 3, y, x + k * side / 3,
                              y + side),
                             (x, y + k * side / 3, x + side,
                              y + k * side / 3)):
                    self.drawn.append(pyglet.shapes.Line(
                        *ends, thickness=1.0, color=line, batch=self.batch,
                        group=self.body_group))
        else:
            self.drawn.append(pyglet.shapes.Arc(
                x + side / 2, y + side / 2, side * 0.38, segments=64,
                thickness=1.5, color=line, batch=self.batch,
                group=self.body_group))

    # --- a row of five places --------------------------------------------

    def _row_places(self, left, bottom, width, height):
        look = self.puzzle.data['look']
        if look == 0:
            cell = min(width / 7.2, height * 0.6)
            x0, y0 = self._placed(left + width * 0.1, bottom, width * 0.9,
                                  height * 0.8, cell * 5.4, cell)
            return [(x0 + i * cell * 1.1, y0) for i in range(model.ROW)], \
                cell
        cell = min(width * 0.12, height * 0.3)
        out = []
        for i in range(model.ROW):
            frac = i / (model.ROW - 1)
            x = left + width * 0.1 + frac * (width * 0.8 - cell)
            lift = 1 - (2 * frac - 1) ** 2
            y = bottom + height * 0.06 + lift * (height * 0.62 - cell)
            out.append((x, y))
        return out, cell

    def _draw_row(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        look = p.data['look']
        _f, showing = self._frame(t)
        places, cell = self._row_places(left, bottom, width, height)
        order = framed.port_order(look, model.ROW)
        items = None
        if showing is not None and showing >= 0:
            items = p.data['first'] if showing == 0 else p.data['second']
        for port in range(model.ROW):
            place = order[port]
            x, y = places[place]
            self._card(port, x, y, cell, cell)
            if items is not None:
                self._thing(items[place], x + cell / 2, y + cell * 0.45,
                            cell * 0.27)
            if showing == 1 and place == p.data['marked']:
                self._mark_one(x, y, cell, look)
        self._asked(left + width * 0.04, bottom + height * 0.8, cell * 0.4)

    def _mark_one(self, x, y, cell, look) -> None:
        mark = (200, 40, 40) if look == 0 else (30, 150, 60)
        if look == 0:
            self.drawn.append(pyglet.shapes.Arc(
                x + cell / 2, y + cell * 0.45, cell * 0.42, segments=48,
                thickness=max(2.0, cell * 0.05), color=mark,
                batch=self.batch, group=self.top_group))
        else:
            self.drawn.append(pyglet.shapes.Triangle(
                x + cell * 0.3, y + cell * 1.3, x + cell * 0.7,
                y + cell * 1.3, x + cell / 2, y + cell * 1.08, color=mark,
                batch=self.batch, group=self.top_group))


def _task(cls_name, title, task_id, prefix, kind, look):
    return type(cls_name, (NowThenTask,), {
        'instance': None, 'TITLE': title, 'TASK_ID': task_id,
        'PREFIX': prefix, 'KIND': kind, 'LOOK': look,
        '__doc__': '%s (%s, look %d)' % (title, kind, look)})


WhichMoved = _task('WhichMoved', 'Which Moved?', 'which_moved',
                   'WHICHMOVED', 'moved', 0)
MovedBead = _task('MovedBead', 'Moved Bead', 'moved_bead', 'MOVEDBEAD',
                  'moved', 1)
WhichIsNew = _task('WhichIsNew', 'Which Is New?', 'which_is_new',
                   'WHICHISNEW', 'new', 0)
NewBead = _task('NewBead', 'New Bead', 'new_bead', 'NEWBEAD', 'new', 1)
WhichIsGone = _task('WhichIsGone', 'Which Is Gone?', 'which_is_gone',
                    'WHICHISGONE', 'gone', 0)
GoneBead = _task('GoneBead', 'Gone Bead', 'gone_bead', 'GONEBEAD',
                 'gone', 1)
TradedPlaces = _task('TradedPlaces', 'Traded Places', 'traded_places',
                     'TRADEDPLACES', 'traded', 0)
TradedBeads = _task('TradedBeads', 'Traded Beads', 'traded_beads',
                    'TRADEDBEADS', 'traded', 1)

