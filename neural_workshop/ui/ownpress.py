# -*- coding: utf-8 -*-
"""Own presses, on screen: four plain panels, and a right one that
depends on what was pressed on earlier trials.

Nothing on the screen says what was pressed: the panels look the same
for every answer, a chosen panel is not marked, and the verdict says
only right or wrong.

For the agent boundary: Next in Turn and Stay or Shift have four
ports, one a panel, in reading order; Moving Prize four, one a panel,
the other way round. Presses before
the question is put are ignored.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math

import pyglet

from .. import framed
from .. import ownpress as model
from ..i18n import _
from .framed import FrameTask

RIGHT_WORD, WRONG_WORD = _('Right'), _('Wrong')


class OwnPressTask(FrameTask):
    """A trial whose answer is in the player's own past presses."""

    FAMILY = model

    def __init__(self) -> None:
        self.ledger = model.Ledger()
        super().__init__()

    def start_run(self) -> None:
        self.ledger = model.Ledger()
        super().start_run()

    def _make(self):
        return model.deal(self.KIND, self.rung, rng=self.rng,
                          look=self.LOOK, ledger=self.ledger)

    def _judge(self, passed: bool, message: str) -> None:
        if self.phase != self.PLAY:
            return
        self.ledger.record(self.run.chosen if self.run is not None
                           else None)
        super()._judge(passed, RIGHT_WORD if passed else WRONG_WORD)

    def _mark(self, index: int):
        """No panel is marked, chosen or right."""
        return self.ink, 2

    def _spots(self, left, bottom, width, height):
        """Each panel's corner, in reading order of the layout, and the
        panel's side."""
        layout = self.puzzle.data['layout']
        if layout in ('row', 'column', 'square'):
            cols, rows = {'row': (4, 1), 'column': (1, 4),
                          'square': (2, 2)}[layout]
            cell = min(width * 0.7 / cols, height * 0.9 / rows)
            x0, y0 = self._placed(left + width * 0.1, bottom, width * 0.9,
                                  height, cell * cols, cell * rows)
            return [(x0 + (i % cols) * cell,
                     y0 + (rows - 1 - i // cols) * cell)
                    for i in range(model.PORTS)], cell
        cell = min(width * 0.16, height * 0.3)
        cx, cy = left + width / 2, bottom + height / 2
        if layout == 'diamond':
            r = min(width, height) * 0.32
            pts = [(cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy)]
        elif layout == 'arc':
            pts = [(cx + min(width, height * 1.6) * 0.4 * math.cos(a),
                    bottom + cell * 0.6 + height * 0.55 * math.sin(a))
                   for a in (math.pi * 0.85, math.pi * 0.62,
                             math.pi * 0.38, math.pi * 0.15)]
        else:
            pts = [(cx + (i - 1.5) * cell * 1.4,
                    cy + (cell * 0.6 if i % 2 == 0 else -cell * 0.6))
                   for i in range(4)]
        return [(x - cell / 2, y - cell / 2) for x, y in pts], cell

    def _draw_at(self, left, bottom, width, height, t) -> None:
        look = self.puzzle.data['look']
        spots, cell = self._spots(left, bottom, width, height)
        order = framed.port_order(look, model.PORTS)
        colour = (self._hue() if look == 0 else
                  framed.BEADS[(self.puzzle.data['rim'] * 3 + 1)
                               % framed.THINGS])
        for port in range(model.PORTS):
            x, y = spots[order[port]]
            self._card(port, x + cell * 0.06, y + cell * 0.06, cell * 0.88,
                       cell * 0.88)
            if self.run is not None and self.run.open:
                if look == 0:
                    self.drawn.append(pyglet.shapes.Rectangle(
                        x + cell * 0.32, y + cell * 0.32, cell * 0.36,
                        cell * 0.36, color=colour, batch=self.batch,
                        group=self.text_group))
                else:
                    self.drawn.append(pyglet.shapes.Circle(
                        x + cell / 2, y + cell / 2, cell * 0.2,
                        color=colour, batch=self.batch,
                        group=self.text_group))
        self._asked(left + width * 0.04, bottom + height * 0.85,
                    cell * 0.3)


def _task(cls_name, title, task_id, prefix, kind, look):
    return type(cls_name, (OwnPressTask,), {
        'instance': None, 'TITLE': title, 'TASK_ID': task_id,
        'PREFIX': prefix, 'KIND': kind, 'LOOK': look,
        '__doc__': '%s (%s, look %d)' % (title, kind, look)})


NextInTurn = _task('NextInTurn', 'Next in Turn', 'next_in_turn',
                   'NEXTINTURN', 'cycle', 0)
StayOrShift = _task('StayOrShift', 'Stay or Shift', 'stay_or_shift',
                    'STAYORSHIFT', 'stay', 0)
MovingPrize = _task('MovingPrize', 'Moving Prize', 'moving_prize',
                    'MOVINGPRIZE', 'stay', 1)
