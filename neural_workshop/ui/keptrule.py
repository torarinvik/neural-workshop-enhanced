# -*- coding: utf-8 -*-
"""A rule that holds across trials, on screen: a sign at the start of a
block, then on each trial a filled place and the question.

The sign is drawn in the middle for the first frame of the block's
first trial: a filled disc for *same*, a ring crossed by a bar for
*opposite*. Nothing else says which rule holds or how far into the
block a trial is.

For the agent boundary: Same or Opposite has four ports, one a square,
in reading order. Any press before the question is put ends the trial
unpaid.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import framed
from .. import keptrule as model
from .keptcue import CueTask

SIGN = (60, 60, 70)


class RuleTask(CueTask):
    """A trial of a block whose rule was signed at its start."""

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

    def _draw_at(self, left, bottom, width, height, t) -> None:
        super()._draw_at(left, bottom, width, height, t)
        p = self.puzzle
        f, showing = framed.frame_at(p, t)
        if f != 0 or not showing or p.data['sign'] is None:
            return
        r = min(width, height) * 0.12
        cx, cy = left + width * 0.5, bottom + height * 0.5
        same = p.data['sign'] == 'same'
        if p.data['look'] == 1:
            colour = (40, 150, 70) if same else (140, 70, 200)
            self.drawn.append(pyglet.shapes.Star(
                cx, cy, r, r * 0.45, 6 if same else 4, color=colour,
                batch=self.batch, group=self.top_group))
            return
        if same:
            self.drawn.append(pyglet.shapes.Circle(
                cx, cy, r, color=SIGN, batch=self.batch,
                group=self.top_group))
            return
        self.drawn.append(pyglet.shapes.Arc(
            cx, cy, r, segments=48, thickness=max(3.0, r * 0.18),
            color=SIGN, batch=self.batch, group=self.top_group))
        self.drawn.append(pyglet.shapes.Line(
            cx - r, cy - r, cx + r, cy + r, thickness=max(3.0, r * 0.18),
            color=SIGN, batch=self.batch, group=self.top_group))


class SameOrOpposite(RuleTask):
    """A sign at the start of a block: same place, or opposite."""
    instance = None
    TITLE, TASK_ID, PREFIX = 'Same or Opposite', 'same_or_opposite', \
        'SAMEOROPPOSITE'
    KIND, LOOK = 'rule', 0
