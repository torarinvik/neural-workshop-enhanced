# -*- coding: utf-8 -*-
"""Screen layout helpers.

Every widget is positioned in the coordinates of a reference window of
:data:`DEFAULT_WINDOW_WIDTH` x :data:`DEFAULT_WINDOW_HEIGHT` pixels, and
these helpers scale that to the window the player actually has.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from . import state
from .constants import DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH


def _width() -> int:
    return state.window.width


def _height() -> int:
    return state.window.height


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
    """Scale a reference font size to the current window height."""
    return size * (_height() / DEFAULT_WINDOW_HEIGHT)


def calc_dpi(size: int = 100) -> int:
    """Scale a reference DPI to the current window's diagonal-ish size."""
    return int(size * ((_width() + _height())
                       / (DEFAULT_WINDOW_WIDTH + DEFAULT_WINDOW_HEIGHT)))
