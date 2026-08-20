# -*- coding: utf-8 -*-
"""The saccadic eye exercise: a square that jumps between the edges.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Tuple

import pyglet

from .. import state
from ..geometry import height_center, scale_to_height


class Saccadic:
    """A square that jumps between the screen edges, to exercise the eyes."""

    def __init__(self) -> None:
        self.position = 'left'
        self.counter = 0
        self.radius = scale_to_height(10)
        self.color: Tuple[int, int, int, int] = (0, 0, 255, 255)
        self._shape: pyglet.shapes.Rectangle | None = None

    def tick(self, dt: float) -> None:
        self.counter += 1
        if self.counter == state.cfg.SACCADIC_REPETITIONS:
            self.stop()
        else:
            self.position = 'right' if self.position == 'left' else 'left'

    def start(self) -> None:
        self.position = 'left'
        state.mode.saccadic = True
        self.counter = 0
        pyglet.clock.schedule_interval(self.tick, state.cfg.SACCADIC_DELAY)

    def stop(self) -> None:
        pyglet.clock.unschedule(self.tick)
        state.mode.saccadic = False

    def draw(self) -> None:
        y = height_center()
        x = (self.radius if self.position == 'left'
             else state.window.width - self.radius)
        size = self.radius * 2
        pyglet.shapes.Rectangle(x - self.radius, y - self.radius, size, size,
                                color=self.color).draw()
