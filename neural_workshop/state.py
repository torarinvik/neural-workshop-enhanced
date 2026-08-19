# -*- coding: utf-8 -*-
"""The live singletons that make up a running game.

The original single-file program kept these as module globals and reached
them by bare name from everywhere. Splitting the program into modules
makes that unsafe — ``from .state import cfg`` would capture whatever
``cfg`` happened to be at import time, and switching users rebinds it.

So every module imports *this module* and reads ``state.cfg``,
``state.mode``, ``state.window`` at the moment of use. Nothing here is
populated until :func:`neural_workshop.bootstrap.build_application` runs;
before that every attribute is ``None``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

import pyglet

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, typing only
    from .config import DotDict
    from .gamemode import Mode
    from .stats import Stats
    from .ui.effects import Saccadic
    from .ui.field import Field, Visual
    from .ui.graph import Graph
    from .ui.hud import (Circles, CongratsLabel, GameModeLabel,
                         JaeggiWarningLabel, KeysListLabel, LogoLowerLabel,
                         LogoUpperLabel, NativeBackendLabel, PausedLabel,
                         TitleKeysLabel, TitleMessageLabel, UpdateLabel)
    from .ui.readouts import (AnalysisLabel, AverageLabel, ChartLabel,
                              ChartTitleLabel, TodayLabel,
                              TrialsRemainingLabel)
    from .ui.trialui import (ArithmeticAnswerLabel, FeedbackLabel,
                             SessionInfoLabel, SpaceLabel, ThresholdLabel)
    from .window import MyWindow

# --- configuration and windowing -------------------------------------------

#: Parsed ``config.ini`` for the active user. Rebound by ``set_user``.
cfg: Optional['DotDict'] = None

window: Optional['MyWindow'] = None
batch: Optional[pyglet.graphics.Batch] = None

# --- game objects ----------------------------------------------------------

mode: Optional['Mode'] = None
field: Optional['Field'] = None
visuals: List['Visual'] = []
stats: Optional['Stats'] = None
graph: Optional['Graph'] = None

# --- persistent widgets ----------------------------------------------------

circles: Optional['Circles'] = None
saccadic: Optional['Saccadic'] = None

update_label: Optional['UpdateLabel'] = None
game_mode_label: Optional['GameModeLabel'] = None
jaeggi_warning_label: Optional['JaeggiWarningLabel'] = None
keys_list_label: Optional['KeysListLabel'] = None
logo_upper_label: Optional['LogoUpperLabel'] = None
logo_lower_label: Optional['LogoLowerLabel'] = None
title_message_label: Optional['TitleMessageLabel'] = None
title_keys_label: Optional['TitleKeysLabel'] = None
native_backend_label: Optional['NativeBackendLabel'] = None
paused_label: Optional['PausedLabel'] = None
congrats_label: Optional['CongratsLabel'] = None
session_info_label: Optional['SessionInfoLabel'] = None
threshold_label: Optional['ThresholdLabel'] = None
space_label: Optional['SpaceLabel'] = None
analysis_label: Optional['AnalysisLabel'] = None
chart_title_label: Optional['ChartTitleLabel'] = None
chart_label: Optional['ChartLabel'] = None
average_label: Optional['AverageLabel'] = None
today_label: Optional['TodayLabel'] = None
trials_remaining_label: Optional['TrialsRemainingLabel'] = None
arithmetic_answer_label: Optional['ArithmeticAnswerLabel'] = None

#: One :class:`FeedbackLabel` per active modality; rebuilt on mode change.
input_labels: List['FeedbackLabel'] = []

# --- title screen artwork --------------------------------------------------

brain_icon: Optional[pyglet.sprite.Sprite] = None
brain_graphic: Optional[pyglet.sprite.Sprite] = None

# --- miscellaneous ---------------------------------------------------------

#: Phase of the "press space" pulsating animation, in radians.
angle: float = 0.0

#: Newer release found by the start-up version check, if any.
update_available: bool = False
update_version: str = ''

#: Messages raised before the window existed, shown once it does.
message_queue: List[str] = []


def require(name: str) -> Any:
    """Return singleton *name*, raising a clear error if unbuilt.

    Use in code paths that genuinely cannot proceed without it; most
    call sites run after bootstrap and can read the attribute directly.
    """
    value = globals().get(name)
    if value is None:
        raise RuntimeError(
            'neural_workshop.state.%s is not built yet; '
            'call bootstrap.build_application() first' % name)
    return value
