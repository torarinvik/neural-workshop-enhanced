# -*- coding: utf-8 -*-
"""Switching between windowed and fullscreen while the game runs.

Every widget is positioned from the window size when it is built, and
there is no per-frame layout pass, so changing that size means building
them again. :func:`relayout` does exactly that: a fresh batch, a fresh
set of widgets, and the game state — mode, level, stats, the session in
progress — left alone.

Overlays own their own batches, so each one is asked to re-lay itself
out rather than being rebuilt from here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional, Protocol

import pyglet

from . import runtime, state
from .geometry import scale_to_width


class Relayoutable(Protocol):
    """An overlay that can rebuild itself at the current window size."""

    def relayout(self) -> None: ...


def is_fullscreen() -> bool:
    """True when the window currently owns a whole screen."""
    return bool(state.window is not None and state.window.fullscreen)


def open_overlays() -> List[Relayoutable]:
    """Every overlay currently on screen, innermost last.

    Imported lazily: :mod:`neural_workshop.ui` reaches back into this
    module, and the overlays are not built until something opens one.
    """
    from .ui.menu import Menu
    from .ui.monkeyladder import MonkeyLadder
    from .ui.ncupmonte import NCupMonte
    from .ui.taskhub import TaskHub
    found = [TaskHub.instance, MonkeyLadder.instance, NCupMonte.instance,
             Menu.instance]
    return [screen for screen in found
            if screen is not None and not getattr(screen, 'closed', False)]


def relayout() -> None:
    """Rebuild every widget for the window's current size.

    Safe to call at any time: the session, the level and the stats live
    outside the widgets, so only their pixels move.
    """
    from . import bootstrap
    from .session import respawn_visuals, update_all_labels
    from .ui import cursor

    if state.window is None:
        return
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
