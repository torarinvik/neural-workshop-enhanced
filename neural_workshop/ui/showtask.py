# -*- coding: utf-8 -*-
"""The screen for questions that unfold in time.

A :class:`ShowTask` is a choice task on the clock: its scene is drawn
for the run's time, it may sound (through :class:`Tones`, so the agent
hears exactly what plays), and the answer buttons light up once the
question has been put. A subclass gives ``_make`` (the model's deal)
and ``_draw_scene(left, bottom, width, height, t)``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from pyglet.window import key

from .. import showing
from .clocked import ClockedTask
from .spacetask import ChoiceTask
from .tones import Tones


class ShowTask(Tones, ClockedTask, ChoiceTask):
    """A choice that waits for a scene to play out."""

    MODEL = showing
    #: Seconds a sound may ring past its trial's last note.
    TAIL = 1.0

    def _make(self):
        raise NotImplementedError

    def _clear_trial(self) -> None:
        super()._clear_trial()
        self.puzzle = None
        self.chosen = None

    def _deal(self) -> bool:
        self.puzzle = self._make()
        self.chosen = None
        self.run = showing.Run(self.puzzle)
        self.control = None
        self.last_tick = self.clock()
        self._drop()
        self.message = self.puzzle.question
        notes = getattr(self.puzzle, 'notes', ())
        if notes:
            self._tones_start(notes, self.puzzle.patches,
                              max(n.t + n.dur for n in notes) + self.TAIL)
        return True

    def steer(self, port: int) -> None:
        self.choose(port)

    def choose(self, index: int) -> None:
        if self.phase != self.PLAY or self.run is None:
            return
        self.run.answer(index)
        if self.run.result is not None:
            self.chosen = self.run.chosen
            self._judge(*self.run.result)

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._9:
            self.choose(symbol - key._1)

    def _draw_buttons(self, left, bottom, width, height) -> None:
        if self.run is not None and not self.run.open \
                and self.phase == self.PLAY:
            return
        super()._draw_buttons(left, bottom, width, height)

    def _draw_scene(self, left, bottom, width, height) -> None:
        t = self.run.t if self.run is not None else 0.0
        self._draw_at(left, bottom, width, height, t)

    def _draw_at(self, left, bottom, width, height, t: float) -> None:
        raise NotImplementedError
