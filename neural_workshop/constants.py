# -*- coding: utf-8 -*-
"""Compile-time constants that never change while the game is running.

Anything here is safe to ``from ... import`` by value. Values that *do*
change during a run (debug flags, the active user, the parsed config)
live in :mod:`neural_workshop.runtime` and
:mod:`neural_workshop.state` instead, and must be reached through the
module object so rebinding is visible everywhere.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Final, List

VERSION: Final[str] = '5.0'

#: A user config older than this is renamed to ``*.bak`` and regenerated.
CONFIG_OVERWRITE_IF_OLDER_THAN: Final[str] = '4.8'

FOLDER_RES: Final[str] = 'res'
FOLDER_DATA: Final[str] = 'data'

ATTEMPT_TO_SAVE_STATS: Final[bool] = True
STATS_SEPARATOR: Final[str] = ','

WEB_SITE: Final[str] = 'http://brainworkshop.net/'
WEB_TUTORIAL: Final[str] = 'http://brainworkshop.net/tutorial.html'
# FIXME: Add a tutorial catered to clinical trials.
CLINICAL_TUTORIAL: Final[str] = WEB_TUTORIAL
WEB_DONATE: Final[str] = 'http://brainworkshop.net/donate.html'
WEB_VERSION_CHECK: Final[str] = 'http://brainworkshop.net/version.txt'
WEB_PYGLET_DOWNLOAD: Final[str] = 'http://pyglet.org'
WEB_FORUM: Final[str] = 'https://groups.google.com/group/brain-training'
WEB_MORSE: Final[str] = 'https://en.wikipedia.org/wiki/Morse_code'

#: Seconds before the update check gives up.
TIMEOUT_SILENT: Final[int] = 3

TICKS_MIN: Final[int] = 3
TICKS_MAX: Final[int] = 50

#: Every on-screen size is expressed as a fraction of this reference window.
DEFAULT_WINDOW_WIDTH: Final[int] = 912
DEFAULT_WINDOW_HEIGHT: Final[int] = 684

#: Keep the music player alive between tracks instead of recreating it.
PREVENT_MUSIC_SKIPPING: Final[bool] = True

#: Clinical mode enforces a minimal UI and a tamper-resistant binary log.
CLINICAL_MODE: Final[bool] = False

# --- fonts -----------------------------------------------------------------
# pyglet picks the first family present on the system, so each list runs
# from the most desirable face to one that is guaranteed to exist.

#: Fixed width first: menus align their columns by character count.
FONTLIST: Final[List[str]] = [
    'Courier New', 'Monospace', 'Terminal', 'fixed', 'Fixed',
    'Times New Roman', 'Helvetica', 'Arial',
]

#: Proportional serif, for prose.
FONTLIST_SERIF: Final[List[str]] = [
    'Times New Roman', 'Serif', 'Helvetica', 'Arial',
]
