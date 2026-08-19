# -*- coding: utf-8 -*-
"""Screen layout helpers, and the one place window sizes are named.

Every widget is positioned in the coordinates of a reference window of
:data:`DEFAULT_WINDOW_WIDTH` x :data:`DEFAULT_WINDOW_HEIGHT` pixels, and
these helpers scale that to the window the player actually has.

**Two sizes, and they are not the same number.** On a scaled display
(Retina, Windows display scaling, fractional scaling on Wayland) a
window has:

``pixels``
    the drawing surface. ``window.width``, the GL viewport and every
    widget coordinate are in pixels. This is the space the rest of the
    game works in, and :func:`pixel_size` reports it.
``points``
    what the operating system sizes windows in. ``window.set_size``,
    ``cfg.WINDOW_WIDTH`` and screen dimensions are in points, and
    :func:`point_size` reports it.

``pixels = points * window.scale``, and on an unscaled display the two
are equal — which is exactly why mixing them up survives testing on
one machine and doubles the window on another. pyglet itself gets this
wrong: ``Window.set_fullscreen`` saves the windowed size with
``get_size()`` (pixels) and restores it through ``_width`` (points), so
leaving fullscreen without :func:`set_window_size` doubles the window
on every toggle.

To keep that contained, this module owns every call into pyglet's
point-space API. Nothing else in the game may call ``set_size``,
``get_size``, ``get_framebuffer_size`` or read ``window.scale``;
``tests/test_ui_units.py`` fails the build if that changes. Reading
``window.width`` for layout stays fine everywhere — that is pixels,
and pixels are what widgets want.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Callable, List, Tuple

from . import runtime, state
from .constants import DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH

#: Smallest window we will lay out, in points.
MIN_WINDOW_WIDTH: int = 640
MIN_WINDOW_HEIGHT: int = 480

#: Largest drawing surface we will lay out, in pixels. Well past any
#: real display; the point is that a window manager does not always
#: cap a silly request (a hidden window never does), and widgets sized
#: from the window height are what break first.
MAX_WINDOW_PIXELS: int = 8192

#: Fonts stop growing here. pyglet packs glyphs into a texture atlas
#: with a fixed size, and a font scaled from a huge window overflows it
#: — which surfaces as an AllocatorException from deep inside a label,
#: nowhere near the resize that caused it.
MAX_FONT_SIZE: float = 200.0

#: Called after :func:`set_window_size` changes the window. Registered
#: by :mod:`neural_workshop.display` so a resize is never left
#: un-laid-out just because the platform did not deliver ``on_resize``.
_size_listeners: List[Callable[[], None]] = []


def add_size_listener(callback: Callable[[], None]) -> None:
    """Run *callback* whenever this module resizes the window."""
    if callback not in _size_listeners:
        _size_listeners.append(callback)


def remove_size_listener(callback: Callable[[], None]) -> None:
    """Stop running *callback* on resize."""
    while callback in _size_listeners:
        _size_listeners.remove(callback)


def _size_changed() -> None:
    for callback in list(_size_listeners):
        try:
            callback()
        except Exception as exc:   # a listener must not break resizing
            runtime.debug_msg(exc)


# --- the two coordinate spaces --------------------------------------------

def window_scale() -> float:
    """Pixels per point for the current window. 1.0 on unscaled displays."""
    if state.window is None:
        return 1.0
    try:
        return float(state.window.scale) or 1.0
    except Exception:
        return 1.0


def pixel_size() -> Tuple[int, int]:
    """The drawing surface, in pixels. What widgets and GL work in."""
    if state.window is None:
        return DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
    return int(state.window.width), int(state.window.height)


def framebuffer_size(window: object = None) -> Tuple[int, int]:
    """The buffer ``glReadPixels`` covers, for *window* or the game's.

    Normally identical to :func:`pixel_size`; they can differ under
    pyglet's ``dpi_scaling='stretch'``, where the surface is larger
    than the coordinate space drawn into it.
    """
    window = window if window is not None else state.window
    if window is None:
        return DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
    try:
        width, height = window.get_framebuffer_size()
    except Exception:
        width, height = window.width, window.height
    return int(width), int(height)


def point_size() -> Tuple[int, int]:
    """The window, in the points the operating system sizes it in."""
    width, height = pixel_size()
    return pixels_to_points(width), pixels_to_points(height)


def points_to_pixels(points: float) -> int:
    """Convert an OS-space length to drawing-space pixels."""
    return int(round(points * window_scale()))


def pixels_to_points(pixels: float) -> int:
    """Convert a drawing-space length to OS-space points."""
    return int(round(pixels / window_scale()))


def clamp_points(value: float, minimum: int) -> int:
    """Hold a requested point length inside what we can lay out."""
    ceiling = max(minimum, pixels_to_points(MAX_WINDOW_PIXELS))
    return int(max(minimum, min(ceiling, int(value))))


def apply_minimum_size(window: object) -> None:
    """Stop the player shrinking the window below a layable-out size."""
    try:
        window.set_minimum_size(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
    except Exception as exc:
        runtime.debug_msg(exc)


def set_window_size(width: int, height: int) -> Tuple[int, int]:
    """Resize the window to *width* x *height* **points**.

    The only sanctioned way to resize. Clamps to the minimum size,
    refuses while fullscreen (where pyglet raises), and verifies the
    result — so passing pixels by mistake is reported here instead of
    silently doubling the window.

    Returns the size the window ended up, in points.
    """
    window = state.window
    if window is None:
        return 0, 0
    if window.fullscreen:
        runtime.debug_msg('Ignoring a resize request while fullscreen')
        return point_size()

    wanted = (clamp_points(width, MIN_WINDOW_WIDTH),
              clamp_points(height, MIN_WINDOW_HEIGHT))
    before = point_size()
    try:
        window.set_size(*wanted)
    except Exception as exc:
        runtime.error_msg('Could not resize the window', exc)
        return point_size()

    got = point_size()
    if resize_overshot(wanted, got):
        runtime.error_msg(
            'Window resize overshot: asked for %sx%s points, got %sx%s. '
            'The caller probably passed pixels.' % (wanted + got), None)
    elif got != wanted:
        # Smaller than asked is the window manager fitting the window to
        # the screen, its decorations or a snapped layout. Normal.
        runtime.debug_msg('Window manager sized us %sx%s, not %sx%s'
                          % (got + wanted))
    if got != before:
        _size_changed()
    return got


def resize_overshot(wanted: Tuple[int, int], got: Tuple[int, int]) -> bool:
    """True when a resize came back *bigger* than it was asked for.

    A window manager may hand back a smaller window — the screen, its
    decorations and snapped layouts all cap it — and that is routine.
    Coming back larger is not: it is the signature of points and pixels
    being mixed up, where the window grows by ``window.scale`` every
    time. Only that case is worth shouting about.
    """
    return got[0] > wanted[0] + 1 or got[1] > wanted[1] + 1


# --- reference-window scaling ---------------------------------------------

def _width() -> int:
    return pixel_size()[0]


def _height() -> int:
    return pixel_size()[1]


def from_width_center(offset: float) -> int:
    """*offset* reference pixels right of the window's horizontal centre."""
    return int(_width() / 2 + offset * (_width() / DEFAULT_WINDOW_WIDTH))


def from_height_center(offset: float) -> int:
    """*offset* reference pixels above the window's vertical centre."""
    return int(_height() / 2 + offset * (_height() / DEFAULT_WINDOW_HEIGHT))


def width_center() -> int:
    """Horizontal centre of the window, in pixels."""
    return int(_width() / 2)


def height_center() -> int:
    """Vertical centre of the window, in pixels."""
    return int(_height() / 2)


def from_top_edge(from_edge: float) -> int:
    """*from_edge* reference pixels below the top of the window."""
    return int(_height() - from_edge * _height() / DEFAULT_WINDOW_HEIGHT)


def from_bottom_edge(from_edge: float) -> int:
    """*from_edge* reference pixels above the bottom of the window."""
    return int(from_edge * (_height() / DEFAULT_WINDOW_HEIGHT))


def from_right_edge(from_edge: float) -> int:
    """*from_edge* reference pixels left of the right window edge."""
    return int(_width() - from_edge * _width() / DEFAULT_WINDOW_WIDTH)


def from_left_edge(from_edge: float) -> int:
    """*from_edge* reference pixels right of the left window edge."""
    return int(from_edge * _width() / DEFAULT_WINDOW_WIDTH)


def scale_to_width(fraction: float) -> int:
    """Scale a reference-width length to the current window."""
    return int(fraction * _width() / DEFAULT_WINDOW_WIDTH)


def scale_to_height(fraction: float) -> int:
    """Scale a reference-height length to the current window."""
    return int(fraction * _height() / DEFAULT_WINDOW_HEIGHT)


def calc_fontsize(size: float) -> float:
    """Scale a reference font size to the current window height.

    Capped at :data:`MAX_FONT_SIZE`: past that the glyphs no longer fit
    pyglet's texture atlas, and the failure lands inside label creation
    rather than at the window size that caused it.
    """
    return min(MAX_FONT_SIZE, size * (_height() / DEFAULT_WINDOW_HEIGHT))


def calc_dpi(size: int = 100) -> int:
    """Scale a reference DPI to the current window's diagonal-ish size."""
    return int(size * ((_width() + _height())
                       / (DEFAULT_WINDOW_WIDTH + DEFAULT_WINDOW_HEIGHT)))
