# -*- coding: utf-8 -*-
"""Creation of the single game window.

``MyWindow`` swallows pyglet's default key handling; the real handlers
live in :mod:`neural_workshop.events` and are pushed onto the window
after everything else is built.

The window is resizable, and the layout follows it — see
:mod:`neural_workshop.display`. Sizes here are in **points**, the space
the operating system works in; :mod:`neural_workshop.geometry` explains
why that is not the same as the pixels every widget is drawn in, and
owns the conversion.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import sys

import pyglet

from . import runtime, state
from .constants import CLINICAL_MODE, VERSION
from .geometry import (MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH,
                       apply_minimum_size, point_size, set_window_size)
from .paths import load_pyglet_image


class MyWindow(pyglet.window.Window):
    """A window that ignores keys until the game pushes its handlers."""

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        pass

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        pass


def enter_fullscreen(window: MyWindow) -> None:
    """Take over the default screen and hide the system cursor.

    The windowed size is remembered first: pyglet stores its own copy
    in the wrong coordinate space, so :func:`leave_fullscreen` cannot
    trust it.
    """
    state.cfg.WINDOW_WIDTH, state.cfg.WINDOW_HEIGHT = point_size()
    screen = pyglet.display.get_display().get_default_screen()
    # Screen dimensions are points, like every other OS-space size.
    state.cfg.WINDOW_WIDTH_FULLSCREEN = screen.width
    state.cfg.WINDOW_HEIGHT_FULLSCREEN = screen.height
    window.set_fullscreen(True, screen=screen)
    if sys.platform == 'darwin':
        window.set_exclusive_keyboard()
    window.set_mouse_visible(False)


def leave_fullscreen(window: MyWindow) -> None:
    """Give the screen back, at the size the player last had.

    The explicit resize is not redundant: pyglet saves the windowed
    size in pixels and restores it as points, so on a scaled display
    the window would come back twice as large on every toggle.
    """
    if sys.platform == 'darwin':
        window.set_exclusive_keyboard(False)
    window.set_fullscreen(False)
    set_window_size(state.cfg.WINDOW_WIDTH, state.cfg.WINDOW_HEIGHT)
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
    window = MyWindow(max(MIN_WINDOW_WIDTH, int(cfg.WINDOW_WIDTH)),
                      max(MIN_WINDOW_HEIGHT, int(cfg.WINDOW_HEIGHT)),
                      caption=_caption(),
                      style=pyglet.window.Window.WINDOW_STYLE_DEFAULT,
                      resizable=True, vsync=runtime.VSYNC)
    apply_minimum_size(window)

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
