# -*- coding: utf-8 -*-
"""A cue far back, on screen: one of four things is marked, look-alike
frames go by, and then the question.

For the agent boundary: The Marked One has four ports, one a card,
left to right; its twin Flagged Bead four, one a card, top to bottom.
Presses before the question is put are ignored, and the cards are
blank until it is.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import farcue as model
from .. import framed
from .framed import FrameTask


class FarCueTask(FrameTask):
    """A marked thing, look-alikes, and a question about the mark."""

    FAMILY = model

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        look, data = p.data['look'], p.data
        f, value = self._frame(t)
        if look == 0:
            card = min(width * 0.13, height * 0.2)
            cell = min(width * 0.16, (height - card * 1.5) * 0.9)
            px, py = self._placed(left + width * 0.08, bottom + card * 1.5,
                                  width * 0.92, height - card * 1.5,
                                  cell * 4.4, cell)
            panels = [(px + i * cell * 1.1, py) for i in range(4)]
            x0 = left + (width - card * 4.6) / 2
            places = [(x0 + i * card * 1.2, bottom) for i in range(4)]
        else:
            card = min(height * 0.2, width * 0.13)
            cell = min(height * 0.42, (width - card * 2.4) * 0.4)
            px, py = self._placed(left + width * 0.06, bottom,
                                  width - card * 2.4, height,
                                  cell * 2.2, cell * 2.2)
            panels = [(px + (i % 2) * cell * 1.2,
                       py + (1 - i // 2) * cell * 1.2) for i in range(4)]
            x = left + width - card * 1.25
            y0 = bottom + (height - card * 4.6) / 2
            places = [(x, y0 + i * card * 1.2) for i in range(4)]
        things = None
        if value == 0:
            things = data['first']
        elif value == 1:
            things = data['fillers'][f - 1]
        for i, (x, y) in enumerate(panels):
            self._box(x, y, cell, cell, None, self.ink, thickness=1.5)
            if things is not None:
                self._thing(things[i], x + cell / 2, y + cell / 2,
                            cell * 0.28)
            if value == 0 and i == data['marked']:
                self._mark_one(x, y, cell, look)
        order = framed.port_order(look, model.CARDS)
        for port in range(model.CARDS):
            x, y = places[order[port]]
            self._card(port, x, y, card, card)
            if self.run is not None and self.run.open:
                self._thing(model.card_of(p, port), x + card / 2,
                            y + card * 0.45, card * 0.27)
        self._asked(left + width * 0.03, bottom + height * 0.5, card * 0.4)

    def _mark_one(self, x, y, cell, look) -> None:
        if look == 0:
            self.drawn.append(pyglet.shapes.Arc(
                x + cell / 2, y + cell / 2, cell * 0.44, segments=48,
                thickness=max(2.0, cell * 0.05), color=(200, 40, 40),
                batch=self.batch, group=self.top_group))
        else:
            self.drawn.append(pyglet.shapes.Triangle(
                x + cell * 0.38, y + cell * 0.98, x + cell * 0.62,
                y + cell * 0.98, x + cell / 2, y + cell * 0.84,
                color=(30, 150, 60), batch=self.batch,
                group=self.top_group))


class TheMarkedOne(FarCueTask):
    """Four shapes, one ringed, then look-alikes: which was ringed?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'The Marked One', 'the_marked_one', \
        'THEMARKEDONE'
    KIND, LOOK = 'marked', 0


class FlaggedBead(FarCueTask):
    """Four beads, one flagged, then look-alikes: which was flagged?"""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Flagged Bead', 'flagged_bead', 'FLAGGEDBEAD'
    KIND, LOOK = 'marked', 1
