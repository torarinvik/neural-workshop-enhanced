# -*- coding: utf-8 -*-
"""Creation of the single game window.

``MyWindow`` swallows pyglet's default key handling; the real handlers
live in :mod:`neural_workshop.events` and are pushed onto the window
after everything else is built.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import sys

import pyglet

from . import runtime, state
from .constants import CLINICAL_MODE, VERSION
from .paths import load_pyglet_image


class MyWindow(pyglet.window.Window):
    """A window that ignores keys until the game pushes its handlers."""

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        pass

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        pass


def enter_fullscreen(window: MyWindow) -> None:
    """Take over the default screen and hide the system cursor."""
    screen = pyglet.display.get_display().get_default_screen()
    state.cfg.WINDOW_WIDTH_FULLSCREEN = screen.width
    state.cfg.WINDOW_HEIGHT_FULLSCREEN = screen.height
    window.set_fullscreen(True, screen=screen)
    if sys.platform == 'darwin':
        window.set_exclusive_keyboard()
    window.set_mouse_visible(False)


def leave_fullscreen(window: MyWindow) -> None:
    """Give the screen back, at the size the config asks for."""
    if sys.platform == 'darwin':
        window.set_exclusive_keyboard(False)
    window.set_fullscreen(False)
    window.set_size(state.cfg.WINDOW_WIDTH, state.cfg.WINDOW_HEIGHT)
    window.set_mouse_visible(True)


def _caption() -> str:
    """Title-bar text: product, version and the active profile."""
    parts = ['BW-Clinical ' if CLINICAL_MODE else 'Neural Workshop ', VERSION]
    if runtime.USER != 'default':
        parts.extend((' - ', runtime.USER))
    return ''.join(parts)


def create_window() -> MyWindow:
    """Build the window described by the config and prepare its GL state."""
    cfg = state.cfg
    fullscreen = bool(cfg.WINDOW_FULLSCREEN) and not runtime.HEADLESS
    window = MyWindow(cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT,
                      caption=_caption(),
                      style=pyglet.window.Window.WINDOW_STYLE_DEFAULT,
                      vsync=runtime.VSYNC)

    if sys.platform.startswith('linux'):
        from . import resources
        window.set_icon(load_pyglet_image(
            resources.resourcepaths['misc']['brain'][0]))

    if cfg.BLACK_BACKGROUND:
        pyglet.gl.glClearColor(0, 0, 0, 1)
    else:
        pyglet.gl.glClearColor(1, 1, 1, 1)

    if fullscreen:
        enter_fullscreen(window)

    if runtime.HEADLESS:
        try:
            window.set_visible(False)
        except Exception as exc:
            runtime.debug_msg(exc)
    return window
