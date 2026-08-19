# -*- coding: utf-8 -*-
"""Input handling, drawing, and the trial phase machine.

Four loops drive the game:

``on_mouse_press``  the mouse as an alternative to the match keys
``on_key_press``    everything the keyboard does, per screen
``on_draw``         redraws the window
``update``          the session timer, one tick per ``TICK_DURATION_MS``

The phase machine inside a trial is stimulus → blank → feedback, with
tick budgets planned so the three never overlap and always fit the trial.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import time
import webbrowser
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import pyglet
from pyglet.window import key

import bwaccel

from . import display, runtime, state
from .constants import (CLINICAL_MODE, WEB_DONATE, WEB_FORUM, WEB_MORSE,
                        WEB_SITE, WEB_TUTORIAL)
from .paths import dump_pyglet_info, edit_config_ini
from .session import (end_session, generate_stimulus, new_session,
                      reset_input, toggle_manual_mode, update_all_labels,
                      update_input_labels)
from .timing import (plan_current_trial_phases, set_trial_interval_ms,
                     trial_interval_ms)

#: Digit keys accepted by arithmetic mode, main row and numeric keypad.
_DIGIT_KEYS: Dict[int, str] = {}
for _digit in range(10):
    _DIGIT_KEYS[getattr(key, '_%i' % _digit)] = str(_digit)
    _DIGIT_KEYS[getattr(key, 'NUM_%i' % _digit)] = str(_digit)


# --- mouse -----------------------------------------------------------------

def on_mouse_press(x: int, y: int, button: int, modifiers: int) -> None:
    """In two-modality modes, the mouse buttons are the two match keys."""
    mode = state.mode
    if not mode.started:
        return
    modalities = mode.modalities[mode.mode]
    if len(modalities) != 2 or 'arithmetic' in modalities:
        return
    if button == pyglet.window.mouse.LEFT:
        mode.inputs[modalities[0]] = True
    elif button == pyglet.window.mouse.RIGHT:
        mode.inputs[modalities[1]] = True
    else:
        return
    update_input_labels()


# --- keyboard --------------------------------------------------------------

def _open_graph() -> None:
    state.graph.parse_stats()
    state.graph.graph = state.mode.mode
    state.mode.draw_graph = True


def _on_key_title_screen(symbol: int, modifiers: int) -> None:
    from .ui.gameselect import GameSelect
    from .ui.screens import (ImageSelect, LanguageScreen, OptionsScreen,
                             SoundSelect, UserScreen)
    cfg, mode = state.cfg, state.mode
    if symbol in (key.ESCAPE, key.X):
        state.window.on_close()
    elif symbol == key.SPACE:
        mode.title_screen = False
        if not CLINICAL_MODE:
            from .ui.taskhub import TaskHub
            TaskHub(return_to_title=True)
    elif symbol == key.C and not cfg.JAEGGI_MODE:
        GameSelect()
    elif symbol == key.I and not cfg.JAEGGI_MODE:
        ImageSelect()
    elif symbol == key.H:
        webbrowser.open_new_tab(WEB_TUTORIAL)
    elif symbol == key.D and not CLINICAL_MODE:
        webbrowser.open_new_tab(WEB_DONATE)
    elif symbol == key.V and runtime.DEBUG:
        OptionsScreen()
    elif symbol == key.G:
        _open_graph()
    elif symbol == key.U:
        UserScreen()
    elif symbol == key.L:
        LanguageScreen()
    elif symbol == key.S and not cfg.JAEGGI_MODE:
        SoundSelect()
    elif symbol == key.F:
        webbrowser.open_new_tab(WEB_FORUM)
    elif symbol == key.O:
        edit_config_ini()


def _on_key_graph(symbol: int) -> None:
    if symbol in (key.ESCAPE, key.G, key.X):
        state.mode.draw_graph = False
    elif symbol == key.N:
        state.graph.next_nonempty_mode()
    elif symbol == key.M:
        state.graph.next_style()


def _adjust_level(delta: int) -> None:
    state.mode.back = max(1, state.mode.back + delta)
    state.game_mode_label.flash()
    state.space_label.update()
    state.session_info_label.update()


def _adjust_trials(delta: int) -> None:
    mode = state.mode
    mode.num_trials += delta
    mode.num_trials_total = (mode.num_trials + mode.num_trials_factor
                             * mode.back ** mode.num_trials_exponent)
    state.session_info_label.flash()


def _adjust_speed(faster: bool) -> None:
    ms = trial_interval_ms()
    step = bwaccel.interval_adjust_step(ms)
    set_trial_interval_ms(ms - step if faster else ms + step)
    state.session_info_label.flash()


def _on_key_hub(symbol: int, modifiers: int) -> None:
    """Keys on the workshop hub, between sessions."""
    from .ui.gameselect import GameSelect
    from .ui.screens import ImageSelect, SoundSelect, UserScreen
    cfg, mode = state.cfg, state.mode

    if symbol in (key.ESCAPE, key.X):
        if CLINICAL_MODE:
            if cfg.SKIP_TITLE_SCREEN:
                state.window.on_close()
            else:
                mode.title_screen = True
            return
        from .ui.taskhub import TaskHub
        TaskHub(return_to_title=not cfg.SKIP_TITLE_SCREEN)
        return
    if symbol == key.SPACE:
        new_session()
        return
    if CLINICAL_MODE:
        # Nothing below this point is reachable in clinical mode.
        return

    if symbol == key.E and cfg.WINDOW_FULLSCREEN:
        state.saccadic.start()
    elif symbol == key.G:
        _open_graph()
    elif symbol == key.F1 and mode.manual and mode.back > 1:
        _adjust_level(-1)
    elif symbol == key.F2 and mode.manual:
        _adjust_level(1)
    elif symbol == key.F3 and mode.manual and mode.num_trials > 5:
        _adjust_trials(-5)
    elif symbol == key.F4 and mode.manual:
        _adjust_trials(5)
    elif symbol == key.F5 and mode.manual:
        _adjust_speed(faster=False)
    elif symbol == key.F6 and mode.manual:
        _adjust_speed(faster=True)
    elif symbol == key.C and (modifiers & key.MOD_CTRL):
        state.stats.clear()
        state.chart_label.update()
        state.average_label.update()
        state.today_label.update()
        mode.progress = 0
        state.circles.update()
    elif symbol in (key.C, key.I, key.S):
        if cfg.JAEGGI_MODE:
            state.jaeggi_warning_label.show()
            return
        {key.C: GameSelect, key.I: ImageSelect, key.S: SoundSelect}[symbol]()
    elif symbol == key.U:
        UserScreen()
    elif symbol == key.W:
        webbrowser.open_new_tab(WEB_SITE)
        if state.update_available:
            state.window.on_close()
    elif symbol == key.M:
        toggle_manual_mode()
        mode.progress = 0
        state.circles.update()
    elif symbol == key.H:
        webbrowser.open_new_tab(WEB_TUTORIAL)
    elif symbol == key.D:
        webbrowser.open_new_tab(WEB_DONATE)
    elif symbol == key.J and ('morse' in cfg.AUDIO1_SETS
                              or 'morse' in cfg.AUDIO2_SETS):
        webbrowser.open_new_tab(WEB_MORSE)


def _on_key_arithmetic(symbol: int) -> None:
    label = state.arithmetic_answer_label
    if symbol in (key.BACKSPACE, key.DELETE):
        label.reset_input()
    elif symbol in (key.MINUS, key.NUM_SUBTRACT):
        label.input('-')
    elif symbol in (key.PERIOD, key.NUM_DECIMAL):
        label.input('.')
    elif symbol in _DIGIT_KEYS:
        label.input(_DIGIT_KEYS[symbol])


def _on_key_in_session(symbol: int, modifiers: int) -> None:
    """Keys while a session is running: match reports and session control."""
    cfg, mode = state.cfg, state.mode
    if symbol in (key.ESCAPE, key.X) and not CLINICAL_MODE:
        end_session(cancelled=True)
    elif symbol == key.P and not CLINICAL_MODE:
        mode.paused = not mode.paused
        state.paused_label.update()
        state.field.crosshair_update()
    elif symbol == key.F8 and not CLINICAL_MODE:
        mode.hide_text = not mode.hide_text
        update_all_labels()
    elif mode.tick != 0 and mode.trial_number > 0:
        if 'arithmetic' in mode.modalities[mode.mode]:
            _on_key_arithmetic(symbol)
        for k in mode.modalities[mode.mode]:
            if k != 'arithmetic' and symbol == cfg['KEY_%s' % k.upper()]:
                mode.inputs[k] = True
                mode.input_rts[k] = time.time() - mode.trial_starttime
                update_input_labels()

    if symbol == cfg.KEY_ADVANCE and mode.flags[mode.mode]['selfpaced']:
        if mode.phase in ('stimulus', 'blank', None):
            _enter_feedback_phase()


def on_key_press(symbol: int, modifiers: int) -> bool:
    """Dispatch a key press to the handler for the current screen."""
    mode = state.mode
    if symbol == key.D and (modifiers & key.MOD_CTRL):
        dump_pyglet_info()
    elif symbol == key.F11:
        display.toggle_fullscreen()
    elif mode.title_screen and not mode.draw_graph:
        _on_key_title_screen(symbol, modifiers)
    elif mode.draw_graph:
        _on_key_graph(symbol)
    elif mode.saccadic:
        if symbol in (key.ESCAPE, key.E, key.X, key.SPACE):
            state.saccadic.stop()
    elif not mode.started:
        _on_key_hub(symbol, modifiers)
    else:
        _on_key_in_session(symbol, modifiers)
    return pyglet.event.EVENT_HANDLED


# --- drawing ---------------------------------------------------------------

def on_draw() -> None:
    """Redraw the window for the current screen."""
    display.ensure_laid_out()
    mode = state.mode
    if mode.shrink_brain:
        return
    state.window.clear()
    if mode.draw_graph:
        state.graph.draw()
    elif mode.saccadic:
        state.saccadic.draw()
    elif mode.title_screen:
        state.brain_graphic.draw()
        state.title_message_label.draw()
        state.title_keys_label.draw()
    else:
        state.batch.draw()
        if not mode.started and not CLINICAL_MODE:
            state.brain_icon.draw()
            state.logo_upper_label.draw()
            state.logo_lower_label.draw()
    for label in state.input_labels:
        label.draw()


# --- the trial phase machine ----------------------------------------------

def _begin_stimulus_phase() -> str:
    """Start (or restart) a trial's visible stimulus."""
    mode = state.mode
    mode.show_missed = False
    if mode.trial_number > 0:
        state.stats.save_input()
    mode.trial_number += 1
    mode.trial_starttime = time.time()
    state.trials_remaining_label.update()

    if mode.trial_number > mode.num_trials_total:
        end_session()
        mode.phase = 'done'
        mode.session_done = True
        return 'done'

    generate_stimulus()
    reset_input()
    mode.phase = 'stimulus'
    mode.phase_elapsed = 0
    mode.tick = 1
    mode.session_done = False
    return 'stimulus'


def _enter_blank_phase() -> str:
    for visual in state.visuals:
        visual.hide()
    state.mode.phase = 'blank'
    state.mode.phase_elapsed = 0
    return 'blank'


def _enter_feedback_phase() -> str:
    for visual in state.visuals:
        visual.hide()
    state.mode.show_missed = True
    update_input_labels()
    state.mode.phase = 'feedback'
    state.mode.phase_elapsed = 0
    return 'feedback'


def trial_tick() -> Optional[str]:
    """Advance the phase machine one scheduler tick.

    Returns the new phase name when a *significant* visual change
    happened (stimulus / blank / feedback / done), else ``None``.
    """
    mode = state.mode
    if not mode.started or mode.paused:
        return None

    plan = plan_current_trial_phases()
    mode.ticks_per_trial = plan['total_ticks']

    if mode.phase == 'done':
        return None
    if mode.phase is None:
        # Negative ticks are the delay before the first trial appears.
        if (not mode.step_mode) and mode.tick < 0:
            mode.tick += 1
            if mode.tick < 1:
                return None
        return _begin_stimulus_phase()

    # Self-paced: hold in the mid-trial blank until the player advances.
    if (mode.flags[mode.mode]['selfpaced'] and mode.phase == 'blank'
            and mode.phase_elapsed >= 1):
        return None

    mode.phase_elapsed += 1
    mode.tick += 1

    if mode.phase == 'stimulus' \
            and mode.phase_elapsed >= plan['stimulus_ticks']:
        if plan['blank_ticks'] > 0:
            return _enter_blank_phase()
        return _enter_feedback_phase()
    if mode.phase == 'blank' and mode.phase_elapsed >= plan['blank_ticks']:
        return _enter_feedback_phase()
    if mode.phase == 'feedback' \
            and mode.phase_elapsed >= plan['feedback_ticks']:
        return _begin_stimulus_phase()
    return None


#: Ticks to run before giving up on reaching the next visual change.
_ADVANCE_GUARD = 100000


def trial_advance_significant() -> Optional[str]:
    """Run ticks until the visual phase changes, or the session ends."""
    for _ in range(_ADVANCE_GUARD + 1):
        changed = trial_tick()
        if changed:
            return changed
    return state.mode.phase


def response_window_open() -> bool:
    """True only while a trial is showing its stimulus."""
    return bool(state.mode.started and state.mode.phase == 'stimulus')


def action_button_names() -> List[str]:
    """The match buttons available in the current mode, in screen order."""
    return [m for m in state.mode.modalities[state.mode.mode]
            if m != 'arithmetic']


def inject_match_action(buttons: Union[Dict[str, bool], Iterable[str]],
                        now: Optional[float] = None) -> Tuple[str, ...]:
    """Apply match-button intentions through the human input path.

    *buttons* names modalities (``'position1'``, ...) or maps them to
    booleans. Unknown or disallowed names are ignored. Reveals nothing
    about correctness.
    """
    mode = state.mode
    if now is None:
        now = time.time()
    allowed = action_button_names()
    if isinstance(buttons, dict):
        names: Sequence[str] = [k for k, v in buttons.items() if v]
    else:
        names = list(buttons)

    start = getattr(mode, 'trial_starttime', now)
    pressed: List[str] = []
    for name in names:
        if name in allowed:
            mode.inputs[name] = True
            mode.input_rts[name] = max(0.0, now - start)
            pressed.append(name)
    if pressed:
        update_input_labels()
    return tuple(pressed)


# --- scheduled callbacks ---------------------------------------------------

def update(dt: float) -> None:
    """Session timer. Period is ``cfg.TICK_DURATION_MS``."""
    if state.mode.step_mode:
        return
    trial_tick()


def pulsate(dt: float) -> None:
    """Breathe the colour of the "press space" prompt."""
    if state.mode.started or not state.window.visible:
        return
    state.angle = (state.angle + 15) % 360
    blue = 191 + min(64, int(80 * math.cos(math.radians(state.angle))))
    state.space_label.label.color = (0, 0, blue, 255)
