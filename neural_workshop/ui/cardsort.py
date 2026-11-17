# -*- coding: utf-8 -*-
"""Card Sort on screen: key cards along the top, the card to sort below.

For the agent boundary: port k puts the card under key k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import cardsort as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import glyphpaint
from .glyphtask import row
from .spacetask import ChoiceTask


class CardSort(ChoiceTask):
    """Sort by the rule nobody states, and notice when it changes."""

    instance: Optional['CardSort'] = None

    TITLE = 'Card Sort'
    TASK_ID = 'card_sort'
    PREFIX = 'CARDSORT'
    CATEGORY = 'reasoning'
    BUTTONS = 0
    FEEDBACK = 1.2
    FOOTNOTE = _('click the key card or press its number   Esc: menu')

    def __init__(self) -> None:
        self.sorter: Optional[model.Sorter] = None
        super().__init__()

    def start_run(self) -> None:
        self.sorter = model.Sorter(self.rng.randrange(1 << 30))
        super().start_run()

    def _make(self):
        if self.sorter is None:
            self.sorter = model.Sorter(self.rng.randrange(1 << 30))
        p = self.sorter.next(self.rung)
        return p

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.puzzle.changed and self.puzzle.level.told:
            self.message = _('The rule has changed!  ') + self.puzzle.question
        return ok

    def choose(self, index: int) -> None:
        if self.phase != self.PLAY or self.puzzle is None \
                or not 0 <= index < len(self.puzzle.choices):
            return
        right = index == self.puzzle.answer
        self.sorter.judged(right)
        super().choose(index)

    def _verdict(self, right: bool) -> str:
        return _('Right') if right else _('Wrong')

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        lk = p.look
        keys = row(left, bottom + height * 0.5, width, height * 0.5,
                   len(p.keys), gap=0.05)
        for k, (x, y, s) in enumerate(keys):
            border, thick = self._mark(k)
            glyphpaint.panel(self, lk, x, y, s, s * 1.0,
                             border=border if thick > 2 else None,
                             thick=thick, paper=(252, 252, 248))
            glyphpaint.glyph(self, lk, p.keys[k], x, y, s, s)
            self._text(str(k + 1), x + s * 0.08, y + s * 0.9,
                       calc_fontsize(12), anchor='left', bold=True,
                       colour=(90, 90, 100, 255))
            self.hits.append((x, y, s, s, lambda c=k: self.choose(c)))
        s = height * 0.42
        x, y = left + (width - s) / 2, bottom + height * 0.02
        glyphpaint.panel(self, lk, x, y, s, s, paper=(255, 255, 255))
        glyphpaint.glyph(self, lk, p.card, x, y, s, s)
