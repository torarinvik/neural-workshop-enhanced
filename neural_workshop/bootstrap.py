# -*- coding: utf-8 -*-
"""Building a running game, in the one order that works.

Nothing in the package touches a singleton until :func:`build_application`
has populated :mod:`neural_workshop.state`. The order matters: the config
decides the window, the window decides every widget's size, and the
widgets need the resources to already be indexed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import socket
import sys
import urllib.request

import pyglet

from . import (audio, config, display, events, resources, runtime,
               state)
from .constants import (CLINICAL_MODE, TIMEOUT_SILENT, VERSION,
                        WEB_VERSION_CHECK)
from .gamemode import Mode
from . import geometry
from .geometry import from_bottom_edge, scale_to_height, scale_to_width
from .paths import ensure_data_dir, load_pyglet_image, quit_with_error
from .stats import Stats
from .timing import apply_trial_interval_override, tick_duration_ms, trial_interval_ms
from .window import create_window
from .i18n import _


def update_check() -> None:
    """Ask the web site whether a newer release exists."""
    socket.setdefaulttimeout(TIMEOUT_SILENT)
    try:
        with urllib.request.urlopen(
                urllib.request.Request(WEB_VERSION_CHECK)) as response:
            version = response.readline().strip().decode('utf-8')
    except Exception as exc:
        runtime.debug_msg(exc)
        return
    if version > VERSION:  # plain string comparison is good enough here
        state.update_available = True
        state.update_version = version


def _check_audio_driver() -> None:
    driver = pyglet.media.get_audio_driver()
    runtime.debug_msg('Loaded audio driver=' + driver.__class__.__name__)
    if driver.__class__.__name__ == 'SilentDriver' and not runtime.HEADLESS:
        quit_with_error(_('No suitable audio driver could be loaded.'))


def _verify_batch_works() -> None:
    """Fail loudly here rather than mysteriously on the first frame."""
    try:
        probe = pyglet.shapes.Rectangle(100, 100, 100, 100, color=(0, 0, 0),
                                        batch=state.batch)
        probe.delete()
    except Exception as exc:
        runtime.debug_msg(exc)
        quit_with_error(_('Error creating test polygon. Full text of error:\n'))


def _build_game_objects() -> None:
    """Create the singletons that outlive a re-layout."""
    state.mode = Mode()
    state.stats = Stats()


def _build_widgets() -> None:
    """Create every persistent widget, in dependency order.

    Everything here is positioned from the current window size and
    lives in :data:`state.batch`, so a window resize rebuilds the lot
    (see :func:`neural_workshop.display.relayout`). Nothing here may
    own game state — that belongs in :func:`_build_game_objects`.
    """
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
    from .ui.trialui import (ArithmeticAnswerLabel, SessionInfoLabel,
                             SpaceLabel, ThresholdLabel)

    state.field = Field()
    state.visuals = [Visual() for _ in range(4)]
    state.graph = Graph()
    state.circles = Circles()
    state.saccadic = Saccadic()

    state.update_label = UpdateLabel()
    state.game_mode_label = GameModeLabel()
    state.jaeggi_warning_label = JaeggiWarningLabel()
    state.keys_list_label = KeysListLabel()
    state.logo_upper_label = LogoUpperLabel()
    state.logo_lower_label = LogoLowerLabel()
    state.title_message_label = TitleMessageLabel()
    state.title_keys_label = TitleKeysLabel()
    state.native_backend_label = NativeBackendLabel()
    state.paused_label = PausedLabel()
    state.congrats_label = CongratsLabel()
    state.session_info_label = SessionInfoLabel()
    state.threshold_label = ThresholdLabel()
    state.space_label = SpaceLabel()
    state.analysis_label = AnalysisLabel()
    state.chart_title_label = ChartTitleLabel()
    state.chart_label = ChartLabel()
    state.average_label = AverageLabel()
    state.today_label = TodayLabel()
    state.trials_remaining_label = TrialsRemainingLabel()
    state.arithmetic_answer_label = ArithmeticAnswerLabel()
    state.input_labels = []


#: Reference-pixel room the title logo gets: the gap between the version
#: banner above it and the key list below. The artwork is fitted to this
#: rather than drawn at whatever resolution the file happens to be, so a
#: replacement logo cannot land half off the screen.
SPLASH_WIDTH = 360
SPLASH_HEIGHT = 316
SPLASH_BOTTOM = 268


def _load_title_artwork() -> None:
    """The brain icon on the hub and the splash image on the title screen."""
    misc = resources.resourcepaths['misc']
    state.brain_icon = pyglet.sprite.Sprite(
        load_pyglet_image(random.choice(misc['brain'])))
    state.brain_icon.position = (
        state.field.center_x - state.brain_icon.width // 2,
        state.field.center_y - state.brain_icon.height // 2, 0)

    splash = 'splash-black' if state.cfg.BLACK_BACKGROUND else 'splash'
    state.brain_graphic = pyglet.sprite.Sprite(
        load_pyglet_image(random.choice(misc[splash])))
    _place_splash()


def _place_splash(fraction: float = 1.0) -> None:
    """Size the title logo to *fraction* of the room it is allowed."""
    graphic = state.brain_graphic
    room_width = scale_to_width(SPLASH_WIDTH)
    room_height = scale_to_height(SPLASH_HEIGHT)
    graphic.scale = fraction * min(room_width / graphic.image.width,
                                   room_height / graphic.image.height)
    graphic.position = (
        state.field.center_x - graphic.width // 2,
        from_bottom_edge(SPLASH_BOTTOM) + (room_height - graphic.height) // 2,
        0)


def scale_brain(fraction: float) -> None:
    """Shrink the splash logo into the hub icon. Scheduled per frame."""
    _place_splash(fraction)
    state.window.clear()
    state.brain_graphic.draw()
    if state.brain_graphic.width < 56:
        state.mode.shrink_brain = False
        pyglet.clock.unschedule(scale_brain)
        _place_splash()


def _restore_last_mode() -> None:
    """Resume the mode and level the player last used."""
    state.stats.initialize_session()
    state.stats.parse_statsfile()
    if state.stats.full_history and not state.cfg.JAEGGI_MODE:
        state.mode.mode = state.stats.full_history[-1][1]
    state.stats.retrieve_progress()
    apply_trial_interval_override()


def _install_handlers() -> None:
    state.window.push_handlers(
        on_key_press=events.on_key_press,
        on_draw=events.on_draw,
        on_mouse_press=events.on_mouse_press,
        on_resize=display.on_resize)
    geometry.add_size_listener(display.request_relayout)
    pyglet.clock.schedule_interval(events.update, runtime.TICK_DURATION)


def build_application() -> None:
    """Build the whole game. Safe to call only once per process."""
    from .session import update_all_labels
    from .ui.message import Message

    if state.window is not None:
        return

    runtime.apply_command_line_flags()
    if '--dump' in sys.argv:
        from .paths import dump_pyglet_info
        dump_pyglet_info()

    ensure_data_dir()
    config.load_last_user('defaults.ini')
    state.cfg = config.load_configuration()

    if state.cfg.VERSION_CHECK_ON_STARTUP and not CLINICAL_MODE:
        update_check()

    # Workaround for pyglet.gl.ContextException on some video cards.
    os.environ['PYGLET_SHADOW_WINDOW'] = '0'
    _check_audio_driver()

    resources.initialize()
    audio.build_players()

    state.window = create_window()
    state.batch = pyglet.graphics.Batch()
    _verify_batch_works()

    _build_game_objects()
    _build_widgets()
    _restore_last_mode()
    update_all_labels()
    _load_title_artwork()
    scale_brain(1.0)

    # Anything raised while loading had nowhere to go; show it now.
    state.message_queue.reverse()
    for msg in list(state.message_queue):
        Message(msg)
    state.message_queue.clear()

    _install_handlers()


def run() -> None:
    """Build the game and enter pyglet's event loop."""
    from .session import new_session
    build_application()
    if runtime.HEADLESS:
        state.mode.title_screen = False
        new_session()
        if runtime.DEBUG:
            runtime.debug_msg(
                'headless session: %i ms/trial, %i ms tick, %i trials'
                % (trial_interval_ms(), tick_duration_ms(),
                   state.mode.num_trials_total))
    pyglet.app.run()
