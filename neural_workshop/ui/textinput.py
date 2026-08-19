# -*- coding: utf-8 -*-
"""A single-line text prompt, used for entering a new user name.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Callable, List, Optional

import pyglet
from pyglet.window import key

from .. import state


class TextInputScreen:
    """Prompt for one line of text, calling *callback* when accepted."""

    #: Width and height of the input box, in pixels.
    BOX_SIZE = (400, 28)

    def __init__(self, title: str = '', text: str = '',
                 callback: Optional[Callable[[str], object]] = None) -> None:
        window = state.window
        self.titletext = title
        self.starttext = text
        self.input_text: List[str] = []
        self.callback = callback or (lambda value: value)
        self.cursor_pos = 0
        self.cursor_visible = True

        self.bgcolor = (255 * int(not state.cfg.BLACK_BACKGROUND),) * 3
        self.textcolor = (255 * int(state.cfg.BLACK_BACKGROUND),) * 3 + (255,)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            title, font_size=10, weight='normal', color=self.textcolor,
            batch=self.batch,
            x=int(window.width / 2), y=(window.height * 8) / 10 + 24,
            anchor_x='center', anchor_y='center')

        self.x_input = 250
        self.y_input = (window.height * 8) / 10 - 18
        window.push_handlers(self.on_key_press, self.on_draw, self.on_text)
        pyglet.clock.schedule_interval(self.update_cursor, 0.5)
        self.update_display()

    def on_text(self, text: str) -> None:
        if text.isprintable() and len(text) == 1:
            self.input_text.insert(self.cursor_pos, text)
            self.cursor_pos += 1
            self.update_display()

    def on_key_press(self, sym: int, modifiers: int) -> bool:
        if sym == key.BACKSPACE:
            if self.cursor_pos > 0:
                del self.input_text[self.cursor_pos - 1]
                self.cursor_pos -= 1
        elif sym == key.LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif sym == key.RIGHT:
            self.cursor_pos = min(len(self.input_text), self.cursor_pos + 1)
        elif sym in (key.ESCAPE, key.RETURN, key.ENTER):
            if sym != key.ESCAPE:
                self.callback(''.join(self.input_text))
            self.close()
        self.update_display()
        return pyglet.event.EVENT_HANDLED

    def close(self) -> None:
        self.cursor_pos = 0
        self.input_text = []
        pyglet.clock.unschedule(self.update_cursor)
        state.window.pop_handlers()

    def update_cursor(self, dt: float) -> None:
        self.cursor_visible = not self.cursor_visible
        self.update_display()

    def on_draw(self) -> bool:
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED

    def update_display(self) -> None:
        """Draw the box and the text immediately, outside the batch."""
        width, height = self.BOX_SIZE
        pyglet.shapes.Rectangle(self.x_input, self.y_input, width, height,
                                color=(200, 200, 200)).draw()
        cursor = '_' if self.cursor_visible else ' '
        display_text = (''.join(self.input_text[:self.cursor_pos]) + cursor
                        + ''.join(self.input_text[self.cursor_pos:]))
        pyglet.text.Label(display_text, font_size=12, x=self.x_input + 4,
                          y=self.y_input + 14, anchor_y='center').draw()
