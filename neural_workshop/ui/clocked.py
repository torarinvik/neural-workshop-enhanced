# -*- coding: utf-8 -*-
"""The shared frame for clocked control tasks.

A task built on this holds one model run in ``self.run`` and keeps it
moving: every frame it advances the run in small steps, passing it the
control that is on for that frame -- the port the agent sent, else
whatever the held keys say -- and judges the trial when the run has a
result. Ports in the model's ``EVENTS`` act once, when they arrive;
every other port is a control that lasts the frame it was sent in.

Scenery that never moves is built once per trial (and per batch and
frame size) by ``_build_scenery`` into ``self.scenery``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import List, Optional

from pyglet.window import key

from .. import state
from .rungtask import RungTask


class ClockedTask(RungTask):
    """A RungTask whose model runs on the clock."""

    #: The model module: deal(rung, rng=), Run(dealt), Run.step(dt,
    #: control), Run.result, EVENTS and act(run, port).
    MODEL = None
    #: Seconds per physics step.
    SUBSTEP = 1 / 120.0
    #: Discrete ports by key symbol; and held keys for controls.
    EVENT_KEYS = {}

    def __init__(self) -> None:
        self.run = None
        self.control: Optional[int] = None
        self.last_tick = 0.0
        self.scenery: List[object] = []
        self.scenery_key = None
        self.keys = key.KeyStateHandler()
        super().__init__()
        state.window.push_handlers(self.keys)

    def close(self) -> None:
        if type(self).instance is self:
            self._drop()
            try:
                state.window.remove_handlers(self.keys)
            except Exception:
                pass
        super().close()

    def _drop(self) -> None:
        for item in self.scenery:
            try:
                item.delete()
            except Exception:
                pass
        self.scenery = []
        self.scenery_key = None

    def _clear_trial(self) -> None:
        self.run = None
        self._drop()

    def _deal(self) -> bool:
        self.run = self._make_run()
        self.control = None
        self.last_tick = self.clock()
        self._drop()
        return True

    def _make_run(self):
        model = self.MODEL
        return model.Run(model.deal(self.rung, rng=self.rng))

    # --- controls -----------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY or self.run is None:
            return
        if port in self.MODEL.EVENTS:
            self.MODEL.act(self.run, port)
        else:
            self.control = port

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in self.EVENT_KEYS:
            self.steer(self.EVENT_KEYS[symbol])

    def _held(self) -> Optional[int]:
        return None

    def _tick(self) -> None:
        now = self.clock()
        dt = max(0.0, min(0.1, now - self.last_tick))
        self.last_tick = now
        control = self.control if self.control is not None else \
            self._held()
        self.control = None
        run = self.run
        steps = max(1, int(math.ceil(dt / self.SUBSTEP)))
        for _s in range(steps):
            run.step(dt / steps, control)
            if run.result is not None:
                break
        if run.result is not None:
            self._judge(*run.result)
        else:
            self._redraw()

    # --- scenery ------------------------------------------------------------------

    def _scenery_fresh(self, *extra) -> bool:
        """Whether the cached scenery still fits; rebuilds it if not."""
        want = (id(self.batch), id(self.run)) + tuple(extra)
        if self.scenery_key != want:
            self._drop()
            self._build_scenery()
            self.scenery_key = want
            return False
        return True

    def _build_scenery(self) -> None:
        pass
