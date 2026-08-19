# -*- coding: utf-8 -*-
"""Shared setup for the user-interface tests.

Importing this module configures a fast headless run and builds the
application, which is a side effect every UI test depends on.
``UI_IMPORT_ERROR`` is not None when no GL context could be created,
and every test module skips itself in that case.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')
os.environ.setdefault('NW_TICK_MS', '1')
os.environ.setdefault('NW_TRIAL_MS', '10')

warnings.filterwarnings('ignore', category=ResourceWarning)

try:
    import pyglet
    from pyglet.window import key

    from neural_workshop import bootstrap, display, state
    from neural_workshop.events import (on_draw, on_key_press,
                                        trial_advance_significant)
    from neural_workshop.geometry import scale_to_height
    from neural_workshop.grid import (current_3d_color_count,
                                      current_active_position_ids,
                                      current_cell_count, decode_3d_colors,
                                      decode_3d_pattern)
    from neural_workshop.session import end_session, new_session
    from neural_workshop.ui import cursor, taskoptions
    from neural_workshop.ui.gameselect import GameSelect
    from neural_workshop.ui.menu import AllCycler, Cycler, Menu, PercentCycler
    from neural_workshop.ui.monkeyladder import MonkeyLadder
    from neural_workshop.ui.ncupmonte import NCupMonte
    from neural_workshop.ui.screens import (ImageSelect, LanguageScreen,
                                            OptionsScreen, SoundSelect,
                                            UserScreen)
    from neural_workshop.ui.taskhub import TASKS, TaskHub, tasks_for
    bootstrap.build_application()
    UI_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - no GL context available
    UI_IMPORT_ERROR = exc


def needs_ui(cls):
    """Skip *cls* when the application could not be built."""
    return unittest.skipIf(
        UI_IMPORT_ERROR is not None,
        'cannot build application: %s' % (UI_IMPORT_ERROR,))(cls)


def close_overlays() -> None:
    """Shut every overlay that a test may have left open."""
    for screen in (Menu.instance, MonkeyLadder.instance, NCupMonte.instance,
                   TaskHub.instance):
        if screen is not None and not getattr(screen, 'closed', False):
            screen.close()
