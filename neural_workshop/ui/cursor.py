# -*- coding: utf-8 -*-
"""The pointing-hand cursor worn by the mouse-driven tasks.

Tasks the player clicks through — the task hub, Monkey Ladder, N-Cup
Monte — swap the system arrow for the hand in ``res/misc/cursor``.
Tasks played from the keyboard leave the cursor alone.

The artwork is authored large (512 px square is typical), so it is
drawn through OpenGL at a window-relative size rather than handed to
the operating system, which would render it at its native size. The
hot spot is measured from the image: the topmost row that is not
transparent, centred horizontally, which is the fingertip of any
pointing cursor.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional, Tuple

import pyglet
from pyglet import gl

from .. import runtime, state
from ..geometry import scale_to_height
from ..paths import load_pyglet_image

#: Cursor height in reference-window pixels, scaled to the real window.
CURSOR_HEIGHT: int = 34

#: Alpha above which a pixel counts as part of the artwork.
_OPAQUE: int = 24

#: Rows to search for the fingertip before giving up on the top edge.
_TIP_SEARCH_ROWS: int = 64

#: Built once per window size, keyed by the height it was built for.
_cursor: Optional[pyglet.window.ImageMouseCursor] = None
_cursor_height: int = 0

#: How many screens currently want the hand.
_holders: int = 0


def _fingertip(data: pyglet.image.ImageData) -> Tuple[float, float]:
    """The hot spot of *data*, as fractions of its width and height.

    Scans down from the top for the first row containing artwork and
    takes its horizontal centre. Falls back to the top-left corner,
    which is what a cursor with no visible tip should use anyway.
    """
    width, height = data.width, data.height
    if width < 1 or height < 1:
        return 0.0, 1.0
    pixels = data.get_data('RGBA', width * 4)
    for offset in range(min(_TIP_SEARCH_ROWS, height)):
        row = height - 1 - offset          # pyglet rows run bottom-up
        base = row * width * 4
        columns = [x for x in range(width)
                   if pixels[base + x * 4 + 3] > _OPAQUE]
        if columns:
            centre = (columns[0] + columns[-1] + 1) / 2.0
            return centre / width, (height - offset) / height
    return 0.0, 1.0


def _mipmapped_texture(data: pyglet.image.ImageData) -> pyglet.image.Texture:
    """A texture of *data* with a usable mipmap chain.

    ``ImageData.get_mipmapped_texture`` calls ``glGenerateMipmap``
    before it uploads level 0, so the smaller levels are built from
    undefined data and the texture is incomplete. Uploading first and
    generating after is the same handful of calls, done in order.
    """
    # Storage but no pixels: blit_to_texture fills level 0 below.
    texture = pyglet.image.Texture.create(
        data.width, data.height, gl.GL_TEXTURE_2D, blank_data=False)
    gl.glBindTexture(texture.target, texture.id)
    gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MIN_FILTER,
                       gl.GL_LINEAR_MIPMAP_LINEAR)
    gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    data.blit_to_texture(texture.target, texture.level, 0, 0, 0)
    gl.glGenerateMipmap(texture.target)
    return texture


def _build(height: int) -> Optional[pyglet.window.ImageMouseCursor]:
    """Load the artwork and wrap it in a cursor *height* pixels tall."""
    from .. import resources
    paths = resources.resourcepaths.get('misc', {}).get('cursor')
    if not paths:
        return None
    try:
        data = load_pyglet_image(paths[0]).get_image_data()
        hot_x_fraction, hot_y_fraction = _fingertip(data)
        # Mipmaps: the artwork is far larger than the drawn size, and
        # plain linear minification of a 512 px hand is visibly ragged.
        texture = _mipmapped_texture(data)
    except Exception as exc:
        runtime.debug_msg(exc)
        return None
    width = max(1, int(round(height * data.width / float(data.height))))
    texture.width = width
    texture.height = height
    return pyglet.window.ImageMouseCursor(
        texture, hot_x=hot_x_fraction * width, hot_y=hot_y_fraction * height)


def hand_cursor() -> Optional[pyglet.window.ImageMouseCursor]:
    """The hand cursor at the current window size, or ``None``.

    Returns ``None`` when the artwork is missing or will not load, so
    every caller degrades to the system cursor.
    """
    global _cursor, _cursor_height
    height = max(8, scale_to_height(CURSOR_HEIGHT))
    if _cursor is None or _cursor_height != height:
        built = _build(height)
        if built is None:
            return None
        _cursor, _cursor_height = built, height
    return _cursor


def acquire() -> None:
    """Show the hand for a screen that has just opened."""
    global _holders
    _holders += 1
    cursor = hand_cursor()
    if cursor is None:
        _show_system_cursor()
        return
    try:
        state.window.set_mouse_cursor(cursor)
        state.window.set_mouse_visible(True)
    except Exception as exc:
        runtime.debug_msg(exc)


def release() -> None:
    """Give the cursor back when a screen closes.

    Screens nest — the hub opens a task, a task opens its options — so
    the arrow only returns once the last of them is gone.
    """
    global _holders
    _holders = max(0, _holders - 1)
    if _holders:
        return
    try:
        state.window.set_mouse_cursor(None)
        if state.cfg.WINDOW_FULLSCREEN:
            state.window.set_mouse_visible(False)
    except Exception as exc:
        runtime.debug_msg(exc)


def _show_system_cursor() -> None:
    try:
        state.window.set_mouse_visible(True)
    except Exception as exc:
        runtime.debug_msg(exc)


def holders() -> int:
    """How many open screens are asking for the hand. For tests."""
    return _holders


def reset() -> None:
    """Drop the cached cursor, so the next use rebuilds it."""
    global _cursor, _cursor_height, _holders
    _cursor, _cursor_height, _holders = None, 0, 0
