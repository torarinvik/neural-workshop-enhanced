# -*- coding: utf-8 -*-
"""Keeping the game laid out for whatever size the window is.

Every widget is positioned from the window size when it is built, and
there is no per-frame layout pass, so changing that size means building
them again. :func:`relayout` does exactly that: a fresh batch, a fresh
set of widgets, and the game state — mode, level, stats, the session in
progress — left alone. Overlays own their own batches, so each one is
asked to re-lay itself out rather than being rebuilt from here.

Nothing has to *remember* to call it. :func:`on_resize` is pushed onto
the window at startup, so every cause of a size change — the fullscreen
toggle, the player dragging a corner, a display or scaling change —
arrives through the same path. A rebuild costs enough that a drag would
stutter if it happened per event, so resizes are coalesced into one
rebuild on the next tick; :func:`relayout` itself stays synchronous for
callers that need the new layout immediately.

Window sizes are only ever named in :mod:`neural_workshop.geometry`,
which explains the pixels-versus-points split this module relies on.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional, Protocol, Tuple

import pyglet

from . import runtime, state
from .geometry import pixel_size, point_size, scale_to_width


class Relayoutable(Protocol):
    """An overlay that can rebuild itself at the current window size."""

    def relayout(self) -> None: ...


#: Size the widgets were last built for, so an unchanged size is free.
_laid_out_for: Tuple[int, int] = (0, 0)

#: A resize has arrived and a rebuild is scheduled for the next tick.
_relayout_pending: bool = False

#: Guard against a rebuild that somehow triggers another one.
_relaying_out: bool = False


def is_fullscreen() -> bool:
    """True when the window currently owns a whole screen."""
    return bool(state.window is not None and state.window.fullscreen)


def layout_ready() -> bool:
    """True once there are widgets to lay out.

    ``on_resize`` fires while the window is still being created, before
    :func:`~neural_workshop.bootstrap.build_application` has built
    anything for it to move.
    """
    return state.window is not None and state.field is not None


#: Overlays currently on screen, in the order they opened.
_overlays: List[Relayoutable] = []


def register_overlay(overlay: Relayoutable) -> None:
    """Take part in re-layout for as long as this overlay is on screen.

    Every screen that pushes its own ``on_draw`` must call this, and
    :func:`unregister_overlay` when it closes. A registry rather than a
    hand-kept list of classes, so a screen added later is covered by
    saying so once, in its own constructor.
    """
    if overlay not in _overlays:
        _overlays.append(overlay)


def unregister_overlay(overlay: Relayoutable) -> None:
    """Stop laying out an overlay that has closed."""
    while overlay in _overlays:
        _overlays.remove(overlay)


def open_overlays() -> List[Relayoutable]:
    """Every overlay currently on screen, in the order they opened."""
    return list(_overlays)


def relayout(force: bool = False) -> None:
    """Rebuild every widget for the window's current size.

    Safe to call at any time: the session, the level and the stats live
    outside the widgets, so only their pixels move. Does nothing when
    the window is already the size the widgets were built for, unless
    *force* says to rebuild anyway.
    """
    global _laid_out_for, _relayout_pending, _relaying_out
    _relayout_pending = False
    if not layout_ready() or _relaying_out:
        return
    size = pixel_size()
    if size == _laid_out_for and not force:
        return

    _relaying_out = True
    try:
        _rebuild_everything()
        _laid_out_for = size
    finally:
        _relaying_out = False


def _rebuild_everything() -> None:
    """The rebuild itself. Only :func:`relayout` should call this."""
    from . import bootstrap
    from .session import respawn_visuals, update_all_labels
    from .ui import cursor

    state.batch = pyglet.graphics.Batch()
    bootstrap._build_widgets()
    update_all_labels()
    bootstrap._load_title_artwork()
    bootstrap.scale_brain(scale_to_width(1))
    state.circles.update()
    cursor.reset()

    # A rebuild mid-trial would otherwise blank the stimulus the player
    # is still being asked to remember.
    if state.mode.started and state.mode.phase == 'stimulus':
        respawn_visuals()

    for overlay in open_overlays():
        try:
            overlay.relayout()
        except Exception as exc:  # an overlay must not strand the player
            runtime.debug_msg(exc)


def request_relayout() -> None:
    """Rebuild on the next tick, however many resizes arrive before it."""
    global _relayout_pending
    if _relayout_pending or not layout_ready():
        return
    _relayout_pending = True
    pyglet.clock.schedule_once(_deferred_relayout, 0)


def _deferred_relayout(dt: float) -> None:
    relayout()


def ensure_laid_out() -> None:
    """Lay out before drawing if the window changed size behind our back.

    A tuple compare per frame, and the last word on staleness: however
    the size changed, and whoever forgot to say so, nothing is ever
    drawn against a layout built for a different window.
    """
    if layout_ready() and pixel_size() != _laid_out_for:
        relayout()


def on_resize(width: int, height: int) -> None:
    """Window handler: the size changed, so the layout has to follow.

    Deliberately returns None rather than ``EVENT_HANDLED`` so pyglet's
    own handler still updates the viewport and projection.
    """
    request_relayout()


def remember_window_size() -> None:
    """Store the current windowed size, so leaving fullscreen restores it."""
    if state.window is None or is_fullscreen():
        return
    state.cfg.WINDOW_WIDTH, state.cfg.WINDOW_HEIGHT = point_size()


def set_fullscreen(wanted: bool) -> bool:
    """Enter or leave fullscreen and re-lay the game out.

    Returns whether the window ended up fullscreen, which is not what
    was asked for if the window manager refused.
    """
    from .window import enter_fullscreen, leave_fullscreen

    window = state.window
    if window is None or bool(wanted) == is_fullscreen():
        return is_fullscreen()
    try:
        if wanted:
            enter_fullscreen(window)
        else:
            leave_fullscreen(window)
    except Exception as exc:
        runtime.error_msg('Could not change the window mode', exc)
        return is_fullscreen()

    state.cfg.WINDOW_FULLSCREEN = is_fullscreen()
    # on_resize has already asked for one; do it now so the caller sees
    # the new layout rather than next tick's.
    relayout()
    return is_fullscreen()


def toggle_fullscreen() -> bool:
    """Flip between windowed and fullscreen."""
    return set_fullscreen(not is_fullscreen())


def restore_cursor_visibility() -> None:
    """Show or hide the system cursor to match the window mode."""
    window: Optional[pyglet.window.Window] = state.window
    if window is None:
        return
    try:
        window.set_mouse_visible(not is_fullscreen())
    except Exception as exc:
        runtime.debug_msg(exc)
