#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Neural Workshop entry point and stable public surface.

The implementation lives in the :mod:`neural_workshop` package; this
module is what people and tools actually run and import:

* ``python brainworkshop.py`` starts the game, as it always has.
* ``import brainworkshop as bw`` builds the game and exposes the names
  the agent environment (:mod:`nwenv`) and the tests depend on.

Importing this module has side effects — it creates a window and every
game object — because the agent environment relies on that.

Attributes that get rebound at runtime (``cfg`` when the user switches
profile, the media players) are resolved through ``__getattr__``, so a
caller reading ``bw.cfg`` always sees the current object.

Copyright (C) 2009-2011: Paul Hoskinson (plhosk@gmail.com)
Copyright (C) 2017-2018: Samantha McVey (samantham@posteo.net)
SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys
from typing import Any

if __package__ in (None, ''):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from neural_workshop import VERSION, bootstrap, state  # noqa: E402
from neural_workshop.audio import CapturePlayer  # noqa: E402,F401
from neural_workshop.events import (  # noqa: E402,F401
    action_button_names, inject_match_action, on_draw, on_key_press,
    on_mouse_press, response_window_open, trial_advance_significant,
    trial_tick, update)
from neural_workshop.grid import (  # noqa: E402,F401
    current_active_position_ids, current_cell_count, current_cell_px,
    current_grid_size, position_pixel_center)
from neural_workshop.matching import check_match  # noqa: E402,F401
from neural_workshop.session import (  # noqa: E402,F401
    end_session, generate_stimulus, new_session, reset_input, set_user,
    update_all_labels, update_input_labels)
from neural_workshop.timing import (  # noqa: E402,F401
    plan_current_trial_phases, set_trial_interval_ms, tick_duration_ms,
    trial_interval_ms)

__version__ = VERSION

#: Names resolved live, because the object they point at can be replaced.
_LIVE_STATE = (
    'cfg', 'window', 'batch', 'mode', 'field', 'visuals', 'stats', 'graph',
    'circles', 'saccadic', 'input_labels', 'brain_icon', 'brain_graphic',
    'update_available', 'update_version',
)
_LIVE_AUDIO = ('player', 'player2', 'audio_capture', 'applause_player',
               'music_player')
_LIVE_RUNTIME = ('DEBUG', 'HEADLESS', 'USER', 'CONFIGFILE', 'STATS_BINARY',
                 'TICK_DURATION')

__all__ = sorted(set(_LIVE_STATE) | set(_LIVE_AUDIO) | set(_LIVE_RUNTIME) | {
    'VERSION', 'CapturePlayer', 'action_button_names', 'check_match',
    'current_active_position_ids', 'current_cell_count', 'current_cell_px',
    'current_grid_size', 'end_session', 'generate_stimulus',
    'inject_match_action', 'new_session', 'on_draw', 'on_key_press',
    'on_mouse_press', 'plan_current_trial_phases', 'position_pixel_center',
    'reset_input', 'response_window_open', 'set_trial_interval_ms',
    'set_user', 'tick_duration_ms', 'trial_advance_significant', 'trial_tick',
    'trial_interval_ms', 'update', 'update_all_labels', 'update_input_labels',
})


def __getattr__(name: str) -> Any:
    """Resolve the live singletons at access time, not at import time."""
    if name in _LIVE_STATE:
        return getattr(state, name)
    if name in _LIVE_AUDIO:
        from neural_workshop import audio
        return getattr(audio, name)
    if name in _LIVE_RUNTIME:
        from neural_workshop import runtime
        return getattr(runtime, name)
    raise AttributeError('module %r has no attribute %r' % (__name__, name))


# Importing this module builds the game, as the agent environment expects.
bootstrap.build_application()


if __name__ == '__main__':
    bootstrap.run()
