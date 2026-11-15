# -*- coding: utf-8 -*-
"""Stop & Switch on screen: the rule on top, one stimulus at a time.

The rule sits in a coloured band above the middle (from rung 16 it
lights up only with the stimulus). A stimulus shows in the middle or to
one side; answer with F or Left for left, J or Right for right. A red
ring closing round it means stop. A row of dots along the bottom keeps
the block's score, one per stimulus.

For the agent boundary: port 0 answers left, port 1 right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

import pyglet
from pyglet.window import key

from .. import stopswitch as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask
from .spacetask import RIGHT, WRONG

BLUE = (60, 120, 220)
ORANGE = (236, 140, 40)
STOP = (220, 40, 40)
BANDS = {'shape': (150, 110, 200), 'colour': (60, 170, 160),
         'opposite': (120, 124, 134)}


class StopAndSwitch(RungTask):
    """Answer by the rule, fast -- or not at all."""

    instance: Optional['StopAndSwitch'] = None

    TITLE = 'Stop & Switch'
    TASK_ID = 'stop_and_switch'
    PREFIX = 'STOP_AND_SWITCH'
    CATEGORY = 'self_control'
    FEEDBACK = 2.5
    FOOTNOTE = _('F or Left: left   J or Right: right   red ring: do '
                 'nothing   Esc: menu')

    def __init__(self) -> None:
        self.block: Optional[model.Block] = None
        self.k = 0
        self.shown_at = 0.0
        self.replied: Optional[int] = None
        self.marks: List[bool] = []
        self.showing = False
        self.ring_up = False
        super().__init__()

    def _clear_trial(self) -> None:
        self.block = None
        self.k = 0
        self.marks = []
        self.showing = False

    def _deal(self) -> bool:
        self.block = model.deal(self.rung, rng=self.rng)
        self.k = 0
        self.marks = []
        self._queue(self.clock())
        self.message = _('Answer by the rule; a red ring means stop')
        return True

    def _queue(self, now: float) -> None:
        self.shown_at = now + model.GAP
        self.replied = None
        self.reply_rt: Optional[float] = None
        self.showing = False
        self.ring_up = False

    @property
    def stimulus(self) -> Optional[model.Stimulus]:
        if self.block is None or self.k >= len(self.block.stimuli):
            return None
        return self.block.stimuli[self.k]

    # --- answering -------------------------------------------------------

    def reply(self, way: int) -> None:
        if self.phase != self.PLAY or not self.showing or \
                self.replied is not None:
            return
        self.replied = way
        self.reply_rt = self.clock() - self.shown_at
        self._settle()

    def steer(self, port: int) -> None:
        if port in (model.LEFT, model.RIGHT):
            self.reply(port)

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in (key.F, key.LEFT):
            self.reply(model.LEFT)
        elif symbol in (key.J, key.RIGHT):
            self.reply(model.RIGHT)

    def _settle(self) -> None:
        s = self.stimulus
        self.marks.append(model.right(s, self.replied, self.reply_rt,
                                      self.block.level))
        self.k += 1
        if self.k >= len(self.block.stimuli):
            self._end_block()
            return
        self._queue(self.clock())
        self._redraw()

    def _end_block(self) -> None:
        got = sum(self.marks)
        total = len(self.marks)
        need = self.block.level.needed
        passed = got >= need * total - 1e-9
        self.showing = False
        self._judge(passed, _('%d of %d right (%d needed)')
                    % (got, total, int(-(-need * total // 1))))

    def _tick(self) -> None:
        now = self.clock()
        if not self.showing:
            if now >= self.shown_at:
                self.showing = True
                self._redraw()
            return
        elapsed = now - self.shown_at
        s = self.stimulus
        if s.stop and elapsed >= self.block.level.ssd and \
                not self.ring_up:
            self.ring_up = True
            self._redraw()
        if elapsed >= self.block.level.window:
            self.ring_up = False
            self._settle()

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        block = self.block
        s = self.stimulus
        cx = left + width / 2
        cy = bottom + height * 0.5
        unit = min(width, height) * 0.1
        # The rule.
        if s is not None and (block.level.prepared or self.showing):
            bw, bh = width * 0.3, height * 0.1
            self._box(cx - bw / 2, bottom + height * 0.82, bw, bh,
                      BANDS[s.rule])
            self._text(model.RULES[s.rule], cx, bottom + height * 0.82
                       + bh / 2, min(calc_fontsize(20), bh * 0.5),
                       bold=True, colour=(255, 255, 255, 255))
        # The stimulus, or a fixation point.
        if s is not None and self.showing:
            x = cx + s.side * width * 0.25
            colour = BLUE if s.colour == 'blue' else ORANGE
            if s.shape == 'circle':
                self.drawn.append(pyglet.shapes.Circle(
                    x, cy, unit, color=colour, batch=self.batch,
                    group=self.body_group))
            else:
                self._box(x - unit * 0.9, cy - unit * 0.9, unit * 1.8,
                          unit * 1.8, colour, group=self.body_group)
            if s.stop and self.ring_up:
                self.drawn.append(pyglet.shapes.Arc(
                    x, cy, unit * 1.6, thickness=unit * 0.25, color=STOP,
                    batch=self.batch, group=self.top_group))
        elif s is not None:
            self.drawn.append(pyglet.shapes.Circle(
                cx, cy, unit * 0.12, color=self.ink, batch=self.batch,
                group=self.body_group))
        # The score so far.
        n = len(block.stimuli)
        step = min(width * 0.8 / n, unit * 0.7)
        x0 = cx - step * (n - 1) / 2
        for i in range(n):
            colour = (RIGHT if self.marks[i] else WRONG) \
                if i < len(self.marks) else (200, 202, 208)
            self.drawn.append(pyglet.shapes.Circle(
                x0 + i * step, bottom + height * 0.06, step * 0.3,
                color=colour, batch=self.batch, group=self.body_group))
        # Where left and right are.
        self._text(_('F  left'), left + width * 0.08, bottom + height * 0.5,
                   calc_fontsize(13))
        self._text(_('right  J'), left + width * 0.92,
                   bottom + height * 0.5, calc_fontsize(13))

    def _facts(self) -> str:
        if self.block is None:
            return ''
        return _('rung %d  block %d/%d   %d of %d   %.2f s to answer') % (
            self.rung, self.trial, self.total_trials, sum(self.marks),
            len(self.marks), self.block.level.window)
