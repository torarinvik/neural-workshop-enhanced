# -*- coding: utf-8 -*-
"""Will It Fit? on screen: the piece on the left, the hole or holes cut
in a board on the right.

For the agent boundary: port 0 says yes and 1 no; where there are
holes to choose from, port k picks hole k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import polyomino as P
from .. import willitfit as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import polish, polypaint
from .spacetask import ChoiceTask

BOARD = (196, 160, 110)
HOLE = (40, 34, 30)


class WillItFit(ChoiceTask):
    """Does the piece go into the hole?"""

    instance: Optional['WillItFit'] = None

    TITLE = 'Will It Fit?'
    TASK_ID = 'will_it_fit'
    PREFIX = 'FIT'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')

    def _make(self):
        p = model.deal(self.rung, rng=self.rng)
        self.BUTTONS = 0.13 if len(p.holes) == 1 else 0
        return p

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        cells = [P.size_of(h) for h in p.holes] + [P.size_of(p.piece)]
        span = max(max(a, b) for a, b in cells)
        n = len(p.holes)
        cell = min(height * 0.8 / span, width / (n + 1.6) / span * 0.85)
        ph, pw = P.size_of(p.piece)
        polypaint.shape(self, p.piece, left + width * 0.04,
                        bottom + (height - ph * cell) / 2, cell, p.hue)
        x0 = left + width * 0.04 + span * cell * 1.2
        rest = left + width - x0
        bw = rest / n
        for k, hole in enumerate(p.holes):
            hh, hw = P.size_of(hole)
            x = x0 + k * bw
            border, thick = self._mark(k) if n > 1 else (None, 2)
            polish.card(self.drawn, self.batch, x + bw * 0.04, bottom,
                        bw * 0.92, height, BOARD, radius=10,
                        edge=border if thick > 2 else (150, 120, 80),
                        group=self.card_group)
            polypaint.shape(self, hole, x + (bw - hw * cell) / 2,
                            bottom + (height - hh * cell) / 2, cell, HOLE,
                            edge=(20, 16, 14), hole=True)
            if n > 1:
                self._text(str(k + 1), x + bw * 0.1, bottom + height - 16,
                           calc_fontsize(13), anchor='left', bold=True)
                self.hits.append((x, bottom, bw, height,
                                  lambda c=k: self.choose(c)))
