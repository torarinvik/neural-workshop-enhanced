# -*- coding: utf-8 -*-
"""The mouse, for clocked tasks that steer with it as well as with keys.

Mix in before ClockedTask. While a trial runs, ``self.pointer`` is where
the mouse is (window pixels, or None before it has moved) and
``self.dragged`` the drag since the last frame; ``_drag`` hears each
drag as it comes. The agent boundary has no pointer: every task that
takes the mouse also takes ports that do the same work a notch at a
time, and whatever the mouse does is drawn, so what the screen shows is
the same either way.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional, Tuple

from .. import state


class Pointer:
    """Track the mouse while the task is open."""

    pointer: Optional[Tuple[float, float]] = None
    buttons: int = 0

    def __init__(self) -> None:
        self.pointer = None
        self.buttons = 0
        super().__init__()
        state.window.push_handlers(self.on_mouse_motion, self.on_mouse_drag,
                                   self.on_mouse_release)

    def close(self) -> None:
        if type(self).instance is self:
            try:
                state.window.remove_handlers(self.on_mouse_motion,
                                             self.on_mouse_drag,
                                             self.on_mouse_release)
            except Exception:
                pass
        super().close()

    def on_mouse_motion(self, x, y, dx, dy):
        self.pointer = (float(x), float(y))
        self.buttons = 0

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.pointer = (float(x), float(y))
        self.buttons = buttons
        if self.phase == self.PLAY and self.run is not None:
            self._drag(dx, dy, buttons, modifiers)

    def on_mouse_release(self, x, y, button, modifiers):
        self.buttons = 0

    def _drag(self, dx: float, dy: float, buttons: int,
              modifiers: int) -> None:
        """A drag during play."""
