# -*- coding: utf-8 -*-
"""A modal, full-window notice dismissed by any key.

Messages can be raised before the window exists (during resource
loading); those are printed to the console and queued in
:data:`neural_workshop.state.message_queue` to be shown once it does.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import display, state
from ..geometry import calc_fontsize, height_center, width_center
from ..constants import FONTLIST_SERIF


class Message:
    """A one-shot notice that takes over the window until dismissed."""

    def __init__(self, msg: str) -> None:
        if state.window is None:
            print(msg)                      # console, in case we never show it
            state.message_queue.append(msg)  # and display it once we can
            return
        self.msg = msg
        self.build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        display.register_overlay(self)
        self.on_draw()

    def build_chrome(self) -> None:
        """Create the batch and the label, sized to the window."""
        self.batch = pyglet.graphics.Batch()
        self.label = pyglet.text.Label(
            self.msg,
            font_name=FONTLIST_SERIF,
            color=state.cfg.COLOR_TEXT,
            batch=self.batch,
            multiline=True,
            width=(4 * state.window.width) / 5,
            font_size=calc_fontsize(14),
            x=width_center(), y=height_center(),
            anchor_x='center', anchor_y='center')

    def relayout(self) -> None:
        """Rebuild at the window's current size."""
        self.build_chrome()

    def on_key_press(self, sym: int, mod: int) -> bool:
        if sym:
            self.close()
        return pyglet.event.EVENT_HANDLED

    def close(self) -> None:
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
