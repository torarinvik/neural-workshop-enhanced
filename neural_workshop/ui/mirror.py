# -*- coding: utf-8 -*-
"""Same or Mirror? on screen.

Up to rung 12 two figures side by side and two buttons, Same and Mirror
(or S and M). From rung 13 the figure alone along the top and a row of
numbered figures below: click the one that is the same figure, or press
its number. Every figure is drawn at one scale, so size is no clue.

For the agent boundary: ports 0-4 choose answers 1-5 (Same, Mirror for
a pair).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import mirror as model, space
from ..geometry import calc_fontsize
from ..i18n import _
from . import spacepaint
from .spacetask import ChoiceTask

FIGURE = (214, 176, 112)
FLAT = (226, 214, 190)


class SameOrMirror(ChoiceTask):
    """Is it the same figure turned, or its mirror image?"""

    instance: Optional['SameOrMirror'] = None

    TITLE = 'Same or Mirror?'
    TASK_ID = 'same_or_mirror'
    PREFIX = 'SAME_OR_MIRROR'
    CATEGORY = 'perception'
    FOOTNOTE = _('S: same   M: mirror   or click; from rung 13 click the '
                 'match or press its number   Esc: menu')

    def _make(self):
        puzzle = model.deal(self.rung, rng=self.rng)
        self.BUTTONS = 0.13 if len(puzzle.others) == 1 else 0.0
        return puzzle

    def _key(self, symbol: int, modifiers: int) -> None:
        if self.puzzle is not None and len(self.puzzle.others) == 1:
            if symbol == key.S:
                self.choose(model.SAME)
                return
            if symbol == key.M:
                self.choose(model.MIRROR)
                return
        super()._key(symbol, modifiers)

    def _figure(self, figure, x, y, w, h, reach) -> None:
        """One figure, centred in a box, at the shared scale."""
        colour = FIGURE if self.puzzle.lit else FLAT
        painted = space.render(model.faces(figure, self.puzzle.lit, colour),
                               model.camera())
        scale = min(w, h) * 0.46 / reach
        spacepaint.paint(self, painted,
                         spacepaint.scaled(scale, x + w / 2, y + h / 2),
                         rim_px=max(1.2, scale * 0.04))

    def _draw_scene(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        reach = max(space.radius(f.cubes)
                    for f in (puzzle.reference,) + puzzle.others)
        if len(puzzle.others) == 1:
            w = width / 2
            self._figure(puzzle.reference, left, bottom, w, height, reach)
            self._figure(puzzle.others[0], left + w, bottom, w, height,
                         reach)
            self._box(left + w - 1, bottom + height * 0.1, 2,
                      height * 0.8, (190, 194, 202))
            if self.phase == 'judged':
                self._text(_('%d degrees apart') % round(puzzle.angles[0]),
                           left + width / 2, bottom + 4,
                           calc_fontsize(12), anchor_y='bottom')
            return
        n = len(puzzle.others)
        top_h = height * 0.44
        self._figure(puzzle.reference, left + width / 2 - top_h * 0.7,
                     bottom + height - top_h, top_h * 1.4, top_h, reach)
        gap = width * 0.012
        cw = min((width - gap * (n - 1)) / n, height * 0.6)
        x0 = left + (width - (cw * n + gap * (n - 1))) / 2
        ch = height - top_h - height * 0.04
        for i, figure in enumerate(puzzle.others):
            x = x0 + i * (cw + gap)
            self._card(i, x, bottom, cw, ch)
            self._figure(figure, x, bottom, cw, ch, reach)
