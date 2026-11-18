# -*- coding: utf-8 -*-
"""Which Rule? on screen: three cards, a thing on each, and one hidden
rule for the whole run saying which to press.

For the agent boundary: three ports, one a card, left to right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import ruleguess as model
from ..i18n import _
from .spacetask import ChoiceTask
from .twins import shape


class WhichRule(ChoiceTask):
    """Find the run's hidden rule by pressing."""

    instance: Optional['WhichRule'] = None

    TITLE = 'Which Rule?'
    TASK_ID = 'which_rule'
    PREFIX = 'WHICHRULE'
    CATEGORY = 'first_steps'
    BUTTONS = 0
    FEEDBACK = 1.2
    FOOTNOTE = _('click a card or press 1-3   Esc: menu')

    def __init__(self) -> None:
        self.rule = model.RULES[0]
        self.run_rung = 1
        super().__init__()

    def start_run(self) -> None:
        # The rule and its list of candidates are fixed for the run, so
        # the ladder does not move under them.
        self.run_rung = max(1, self.start_rung)
        self.rule = model.draw_rule(self.run_rung, self.rng)
        super().start_run()

    def _make(self):
        self.rung = self.run_rung
        return model.deal(self.rule, self.run_rung, rng=self.rng)

    def _verdict(self, right: bool) -> str:
        return _('Right') if right else _('No')

    def _facts(self) -> str:
        if self.puzzle is None:
            return ''
        return _('%d/%d   it is one of: %s') % (
            self.trial, self.total_trials,
            ', '.join(model.NAMES[r]
                      for r in model.candidates(self.run_rung)))

    def _draw_scene(self, left, bottom, width, height) -> None:
        card_w = min(width * 0.28, height * 0.8)
        card_h = min(height, card_w * 1.25)
        x0 = left + (width - card_w * 3.3) / 2
        y = bottom + (height - card_h) / 2
        for k, thing in enumerate(self.puzzle.things):
            x = x0 + k * card_w * 1.15
            self._card(k, x, y, card_w, card_h)
            r = card_w * (0.13 + 0.07 * thing.size)
            cx = x + card_w / 2
            cy = y + card_h * (0.27 + 0.2 * thing.height)
            shape(self, thing.shape, cx, cy, r, thing.hue,
                  group=self.text_group, hollow=thing.hollow)
            if thing.dotted:
                self.drawn.append(pyglet.shapes.Circle(
                    cx + r * 1.25, cy + r * 1.05, max(3.0, card_w * 0.035),
                    color=self.ink, batch=self.batch,
                    group=self.top_group))
