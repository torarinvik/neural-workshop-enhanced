# -*- coding: utf-8 -*-
"""The frame-by-frame families on screen: what they share.

A :class:`FrameTask` is a looking-back task whose model deals in one of
two looks (see :mod:`neural_workshop.framed`) and whose run may be
stepped a whole shown frame at a time: its longest tick is a frame, so
an agent boundary driven at two steps a second sees every frame once.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import framed
from .lookback import BackTask
from .twins import shape


class FrameTask(BackTask):
    """A run of frames in one of two looks, judged at the answer."""

    FAMILY = None             # the family's model module
    LOOK = 0
    LONGEST_TICK = framed.FRAME

    def _make(self):
        return self.FAMILY.deal(self.KIND, self.rung, rng=self.rng,
                                look=self.LOOK)

    def _deal(self) -> bool:
        ok = super()._deal()
        self.run = framed.Run(self.puzzle)
        return ok

    def _frame(self, t: float):
        """The frame showing at *t*: its value, or None between."""
        p = self.puzzle
        f, showing = framed.frame_at(p, t)
        return f, (p.frames[f] if showing else None)

    def _hue(self):
        data = self.puzzle.data
        hue = framed.HUES_A[data['hue']]
        return tuple(min(255, c + 70) for c in hue) if self.dark else hue

    def _thing(self, thing: int, cx: float, cy: float, r: float,
               group=None) -> None:
        """One thing: a shape in the trial's hue, or a coloured bead."""
        group = group or self.text_group
        if self.puzzle.data['look'] == 0:
            name, hollow = framed.SHAPES[thing]
            shape(self, name, cx, cy, r, self._hue(), group=group,
                  hollow=hollow)
            return
        rim = framed.RIMS[self.puzzle.data['rim']]
        self.drawn.append(pyglet.shapes.Circle(
            cx, cy, r, color=rim, batch=self.batch, group=group))
        self.drawn.append(pyglet.shapes.Circle(
            cx, cy, r * 0.8, color=framed.BEADS[thing], batch=self.batch,
            group=self.top_group))

    def _placed(self, left, bottom, width, height, w, h):
        """Where a *w* by *h* block sits in the given room: it moves
        from trial to trial."""
        fx, fy = self.puzzle.data.get('place', (0.5, 0.5))
        return (left + max(0.0, width - w) * fx,
                bottom + max(0.0, height - h) * fy)
