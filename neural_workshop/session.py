# -*- coding: utf-8 -*-
"""Running a session: setup, teardown and per-trial stimulus generation.

:func:`generate_stimulus` is the heart of the game. It draws a random
stimulus for each modality, then rewrites some of them so that matches
occur at a controlled rate and near-misses (interference) appear often
enough to make the task hard for the right reason.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
from decimal import Decimal
from typing import List, Optional, Tuple

import pyglet

import bwaccel

from . import audio, resources, runtime, state
from .config import parse_config, rewrite_configfile, save_last_user
from .constants import CLINICAL_MODE, PREVENT_MUSIC_SKIPPING
from .grid import current_active_position_ids
from .paths import get_data_dir


def _pump() -> None:
    """Let the clock run during a long step so music does not skip."""
    if PREVENT_MUSIC_SKIPPING:
        pyglet.clock.tick(poll=True)


# --- labels ----------------------------------------------------------------

def update_all_labels(do_analysis: bool = False) -> None:
    """Refresh every persistent widget from the current game state."""
    state.update_label.update()
    state.congrats_label.update()
    state.analysis_label.update(skip=not do_analysis)
    _pump()

    state.game_mode_label.update()
    state.keys_list_label.update()
    state.paused_label.update()
    state.session_info_label.update()
    state.threshold_label.update()
    state.space_label.update()
    state.chart_title_label.update()
    state.chart_label.update()
    _pump()

    state.average_label.update()
    state.today_label.update()
    state.trials_remaining_label.update()
    state.native_backend_label.update()
    update_input_labels()


def update_input_labels() -> None:
    """Refresh only the per-modality feedback labels."""
    state.arithmetic_answer_label.update()
    for label in state.input_labels:
        label.update()


def reset_input() -> None:
    """Return the match keys to their unpressed state for a new trial."""
    mode = state.mode
    for k in mode.inputs:
        mode.inputs[k] = False
        mode.input_rts[k] = 0.
    state.arithmetic_answer_label.reset_input()
    update_input_labels()


# --- session lifecycle -----------------------------------------------------

def _startup_delay_ticks() -> int:
    """Blank ticks before the first trial, longer when more must load."""
    mode = state.mode
    extra = mode.flags[mode.mode]['multi'] - 1
    ticks = -9 - 5 * extra
    if state.cfg.MULTI_MODE == 'image':
        ticks -= 5 * extra
    return ticks


def _prepare_stimulus_sets() -> None:
    """Pick this session's image set and the eight sounds per channel."""
    from .ui.trialui import generate_input_labels
    cfg, mode = state.cfg, state.mode
    visuals = state.visuals

    mode.sound_mode = random.choice(cfg.AUDIO1_SETS)
    mode.sound2_mode = random.choice(cfg.AUDIO2_SETS)
    audio.audio_capture[:] = []

    visuals[0].load_set()
    visuals[0].choose_random_images(8)
    visuals[0].letters = random.sample(
        list(resources.sounds[mode.sound_mode]), 8)
    visuals[0].letters2 = random.sample(
        list(resources.sounds[mode.sound2_mode]), 8)

    for i in range(1, mode.flags[mode.mode]['multi']):
        visuals[i].load_set(visuals[0].image_set_index)
        visuals[i].choose_indicated_images(visuals[0].image_indices)
        visuals[i].letters = visuals[0].letters
        visuals[i].letters2 = visuals[0].letters2

    # Only now that the images exist can the labels show their icons.
    state.input_labels.extend(generate_input_labels())

    mode.soundlist = [resources.sounds[mode.sound_mode][letter]
                      for letter in visuals[0].letters]
    mode.soundlist2 = [resources.sounds[mode.sound2_mode][letter]
                       for letter in visuals[0].letters2]


def new_session() -> None:
    """Begin a session of the current mode."""
    cfg, mode = state.cfg, state.mode
    mode.tick = 0 if mode.step_mode else _startup_delay_ticks()
    mode.phase = None
    mode.phase_elapsed = 0
    mode.session_done = False
    mode.session_number += 1
    mode.trial_number = 0
    mode.started = True
    mode.paused = False
    state.circles.update()

    _prepare_stimulus_sets()

    if cfg.JAEGGI_MODE:
        compute_bt_sequence()
    _pump()

    if cfg.VARIABLE_NBACK:
        # Beta(n/2, 1) draws, generated in C.
        mode.variable_list = bwaccel.variable_nback_list(
            mode.num_trials_total - mode.back, mode.back)

    state.field.crosshair_update()
    reset_input()
    state.stats.initialize_session()
    update_all_labels()
    pyglet.clock.schedule_interval(audio.fade_out, 0.05)


def _maybe_panhandle() -> None:
    """Ask for a donation every PANHANDLE_FREQUENCY sessions."""
    from .ui.effects import Panhandle
    cfg = state.cfg
    if not cfg.PANHANDLE_FREQUENCY or CLINICAL_MODE:
        return
    statsfile_path = os.path.join(get_data_dir(), cfg.STATSFILE)
    with open(statsfile_path, 'r') as statsfile:
        # Assumes nobody hand-edits their stats file.
        sessions = len(statsfile.readlines())
    if sessions % cfg.PANHANDLE_FREQUENCY == 0:
        Panhandle(n=sessions)


def end_session(cancelled: bool = False) -> None:
    """Finish or abandon the running session."""
    mode = state.mode
    for label in state.input_labels:
        label.delete()
    state.input_labels.clear()

    if cancelled:
        mode.session_number -= 1
    else:
        state.stats.sessions_today += 1
    for visual in state.visuals:
        visual.hide()

    mode.started = False
    mode.paused = False
    mode.phase = 'done'
    mode.session_done = not cancelled
    state.circles.update()
    state.field.crosshair_update()
    reset_input()

    update_all_labels(do_analysis=not cancelled)
    if not cancelled:
        _maybe_panhandle()


def compute_bt_sequence() -> None:
    """Jaeggi mode: a fixed sequence with exactly six matches per stream.

    Built constructively in C, in O(trials). The old nested rejection
    sampler could stall for minutes at a high n-back level.
    """
    mode = state.mode
    ids = current_active_position_ids()
    raw = bwaccel.compute_bt_sequence(
        mode.num_trials_total, mode.back, 6, 6, 2, len(ids), 8)
    mode.bt_sequence = [[ids[i - 1] for i in raw[0]], raw[1]]


# --- stimulus generation ---------------------------------------------------

def _current_and_history_keys(mod: str) -> Tuple[str, str]:
    """Which stimulus a modality shows, and which history it matches."""
    if mod in ('visvis', 'visaudio', 'image'):
        current = 'vis'
    elif mod == 'audiovis':
        current = 'audio'
    else:
        current = mod
    if mod in ('visvis', 'audiovis', 'image'):
        return current, 'vis'
    if mod == 'visaudio':
        return current, 'audio'
    return current, mod


def _sample_random_stimuli() -> List[int]:
    """Draw an independent random value for every stimulus field."""
    mode = state.mode
    active_ids = current_active_position_ids()
    k_multi = min(4, len(active_ids))
    positions = random.sample(active_ids, k_multi)
    for s, p in zip(range(1, k_multi + 1), positions):
        mode.current_stim['position%i' % s] = p
        mode.current_stim['vis%i' % s] = random.randint(1, 8)
    for name in ('color', 'vis', 'audio', 'audio2'):
        mode.current_stim[name] = random.randint(1, 8)
    return positions


def _choose_arithmetic_operands() -> None:
    """Pick the operation and operand for arithmetic mode."""
    cfg, mode = state.cfg, state.mode
    operations = [name for name, enabled in (
        ('add', cfg.ARITHMETIC_USE_ADDITION),
        ('subtract', cfg.ARITHMETIC_USE_SUBTRACTION),
        ('multiply', cfg.ARITHMETIC_USE_MULTIPLICATION),
        ('divide', cfg.ARITHMETIC_USE_DIVISION)) if enabled]
    mode.current_operation = random.choice(operations)

    max_number = cfg.ARITHMETIC_MAX_NUMBER
    min_number = -max_number if cfg.ARITHMETIC_USE_NEGATIVES else 0

    divides = (mode.current_operation == 'divide'
               and 'arithmetic' in mode.modalities[mode.mode])
    if not divides:
        mode.current_stim['number'] = random.randint(min_number, max_number)
        return
    if len(state.stats.session['position1']) < mode.back:
        # No history to divide into yet; any non-zero operand will do.
        number = 0
        while number == 0:
            number = random.randint(min_number, max_number)
        mode.current_stim['number'] = number
        return

    # Only offer divisors that give an acceptable result.
    number_nback = state.stats.session['numbers'][
        mode.trial_number - mode.back - 1]
    acceptable = list(map(Decimal, cfg.ARITHMETIC_ACCEPTABLE_DECIMALS))
    possibilities = []
    for x in range(min_number, max_number + 1):
        if x == 0:
            continue
        if number_nback % x == 0:
            possibilities.append(x)
            continue
        frac = Decimal(abs(number_nback)) / Decimal(abs(x))
        if (frac % 1) in acceptable:
            possibilities.append(x)
    mode.current_stim['number'] = random.choice(possibilities)


def _real_back() -> int:
    """The lag this trial's matches should be planted at."""
    mode = state.mode
    if mode.flags[mode.mode]['crab'] == 1:
        back = 1 + 2 * ((mode.trial_number - 1) % mode.back)
    else:
        back = mode.back
    if state.cfg.VARIABLE_NBACK:
        return mode.variable_list[mode.trial_number - back - 1]
    return back


def _interference_back(back_data: str, real_back: int) -> Optional[int]:
    """A lag near *real_back* whose stimulus differs: a near miss."""
    mode = state.mode
    offsets = [-1, 1, mode.back]
    if real_back < 3:  # crab mode and 2-back cannot look back one further
        offsets = offsets[1:]
    random.shuffle(offsets)
    history = state.stats.session[back_data]
    target = history[mode.trial_number - real_back - 1]
    chosen = real_back
    for offset in offsets:  # keep the last one that works
        index = mode.trial_number - (real_back + offset) - 1
        if index >= 0 and history[index] != target:
            chosen = real_back + offset
    return None if chosen == real_back else chosen


def _resolve_position_conflict(mod: str, current: str, matching_stim: int,
                               positions: List[int], multi: int) -> None:
    """Two stimuli must never land on the same cell; swap if they would."""
    mode = state.mode
    others = set(range(1, multi + 1)) - {int(mod[-1])}
    if matching_stim not in [positions[i - 1] for i in others]:
        return
    i = positions.index(matching_stim)
    if runtime.DEBUG:
        print('moving position%i from %i to %i for %s'
              % (i + 1, positions[i], mode.current_stim[current], current))
    mode.current_stim['position%i' % (i + 1)] = mode.current_stim[current]
    positions[i] = mode.current_stim[current]


def _plant_matches(positions: List[int], multi: int, real_back: int) -> None:
    """Rewrite some stimuli into matches or near-misses."""
    cfg, mode = state.cfg, state.mode
    for mod in mode.modalities[mode.mode]:
        if mod == 'arithmetic':
            continue
        current, back_data = _current_and_history_keys(mod)

        r1, r2 = random.random(), random.random()
        if multi > 1:
            r2 = 3. / 2. * r2  # 33% chance of a multi-stim reversal

        back: Optional[int] = None
        if r1 < cfg.CHANCE_OF_GUARANTEED_MATCH:
            back = real_back
        elif r2 < cfg.CHANCE_OF_INTERFERENCE and mode.back > 1:
            back = _interference_back(back_data, real_back)
            if back is not None and runtime.DEBUG:
                print('Forcing interference for %s' % current)

        if not back:
            continue
        matching_stim = state.stats.session[back_data][
            mode.trial_number - back - 1]
        if multi > 1 and mod.startswith('position'):
            _resolve_position_conflict(mod, current, matching_stim, positions,
                                       multi)
            positions[int(current[-1]) - 1] = matching_stim
        if runtime.DEBUG:
            print('setting %s to %i' % (current, matching_stim))
        mode.current_stim[current] = matching_stim


def _plant_multi_reversal(positions: List[int], multi: int,
                          real_back: int) -> None:
    """Occasionally present the n-back stimuli in a rotated order."""
    cfg, mode = state.cfg, state.mode
    if random.random() >= cfg.CHANCE_OF_INTERFERENCE / 3.:
        return
    field = 'position'
    if 'vis1' in mode.modalities[mode.mode] and random.random() < .5:
        field = 'vis'
    offset = random.choice(range(1, multi))
    for i in range(multi):
        source = '%s%i' % (field, ((i + offset) % multi) + 1)
        value = state.stats.session[source][mode.trial_number - real_back - 1]
        mode.current_stim['%s%i' % (field, i + 1)] = value
        if field == 'position':
            positions[i] = value


def _apply_static_defaults(multi: int) -> None:
    """Stimuli a mode does not use are pinned to a fixed value.

    Position 0 is the centre of the field, colour 1 is red (2 black),
    and vis 0 is a plain square. Audio is never static.
    """
    cfg, mode = state.cfg, state.mode
    modalities = mode.modalities[mode.mode]
    if 'color' not in modalities:
        mode.current_stim['color'] = cfg.VISUAL_COLORS[0]
    if 'position1' not in modalities:
        mode.current_stim['position1'] = 0
    if not {'visvis', 'arithmetic', 'image'} & set(modalities):
        mode.current_stim['vis'] = 0
    if multi > 1 and 'vis1' not in modalities:
        for i in range(1, 5):
            mode.current_stim['vis%i' % i] = (
                0 if cfg.MULTI_MODE == 'color' else cfg.VISUAL_COLORS[0])


def _queue_audio() -> None:
    """Play this trial's sound (or sounds, in dual-audio modes)."""
    cfg, mode = state.cfg, state.mode
    modalities = mode.modalities[mode.mode]
    channel_offsets = {'left': (-99.0, 0.0, 0.0), 'right': (99.0, 0.0, 0.0)}

    if 'arithmetic' in modalities and mode.trial_number > mode.back:
        audio.player.queue(
            resources.sounds['operations'][mode.current_operation])
        audio.player.play()
        return
    if 'audio' not in modalities:
        return

    audio.player.queue(mode.soundlist[mode.current_stim['audio'] - 1])
    if 'audio2' not in modalities:
        audio.player.play()
        return

    audio.player.min_distance = 100.0
    if cfg.CHANNEL_AUDIO1 in channel_offsets:
        audio.player.position = channel_offsets[cfg.CHANNEL_AUDIO1]
    audio.player.play()

    audio.player2.queue(mode.soundlist2[mode.current_stim['audio2'] - 1])
    audio.player2.min_distance = 100.0
    if cfg.CHANNEL_AUDIO2 in channel_offsets:
        audio.player2.position = channel_offsets[cfg.CHANNEL_AUDIO2]
    audio.player2.play()


def _spawn_visuals(multi: int, variable: int) -> None:
    """Show the visual stimuli for this trial."""
    cfg, mode = state.cfg, state.mode
    stim = mode.current_stim
    if multi == 1 or cfg.GRID_3D:
        state.visuals[0].spawn(stim['position1'], stim['color'], stim['vis'],
                               stim['number'], mode.current_operation,
                               variable)
        return
    for i in range(1, multi + 1):
        if cfg.MULTI_MODE == 'color':
            state.visuals[i - 1].spawn(
                stim['position%i' % i], cfg.VISUAL_COLORS[i - 1],
                stim['vis%i' % i], stim['number'], mode.current_operation,
                variable)
        else:
            state.visuals[i - 1].spawn(
                stim['position%i' % i], stim['vis%i' % i], i, stim['number'],
                mode.current_operation, variable)


def generate_stimulus() -> None:
    """Choose and present the stimuli for the next trial."""
    cfg, mode = state.cfg, state.mode
    positions = _sample_random_stimuli()
    _choose_arithmetic_operands()

    multi = mode.flags[mode.mode]['multi']
    real_back = _real_back()

    if mode.modalities[mode.mode] != ['arithmetic'] \
            and mode.trial_number > mode.back:
        _plant_matches(positions, multi, real_back)
        if multi > 1:
            _plant_multi_reversal(positions, multi, real_back)

    _apply_static_defaults(multi)

    if cfg.JAEGGI_MODE:
        mode.current_stim['position1'] = mode.bt_sequence[0][
            mode.trial_number - 1]
        mode.current_stim['audio'] = mode.bt_sequence[1][mode.trial_number - 1]

    _queue_audio()

    if cfg.VARIABLE_NBACK and mode.trial_number > mode.back:
        variable = mode.variable_list[mode.trial_number - 1 - mode.back]
    else:
        variable = 0
    if runtime.DEBUG:
        print('trial=%i, pos=%i, aud=%i, col=%i, vis=%i, num=%i, op=%s, var=%i'
              % (mode.trial_number, mode.current_stim['position1'],
                 mode.current_stim['audio'], mode.current_stim['color'],
                 mode.current_stim['vis'], mode.current_stim['number'],
                 mode.current_operation, variable))
    _spawn_visuals(multi, variable)


# --- users -----------------------------------------------------------------

def toggle_manual_mode() -> None:
    """Switch between the guided curriculum and free choice of level."""
    state.mode.manual = not state.mode.manual
    update_all_labels()


def set_user(newuser: str) -> None:
    """Switch profiles: reload config, stats and progress for *newuser*."""
    runtime.set_user_files(newuser)
    rewrite_configfile(runtime.CONFIGFILE, overwrite=False)
    state.cfg = parse_config(runtime.CONFIGFILE)

    state.stats.initialize_session()
    state.stats.parse_statsfile()
    if state.stats.full_history and not state.cfg.JAEGGI_MODE:
        state.mode.mode = state.stats.full_history[-1][1]
    state.stats.retrieve_progress()

    # The text labels keep the old colours until they are rebuilt, so the
    # background colour is deliberately left alone here.
    state.window.set_fullscreen(state.cfg.WINDOW_FULLSCREEN)
    update_all_labels()
    save_last_user('defaults.ini')


def get_users() -> List[str]:
    """Every profile with a stats file in the data directory."""
    users = ['default'] + [fn.split('-')[0]
                           for fn in os.listdir(get_data_dir())
                           if '-stats.txt' in fn]
    if 'Readme' in users:
        users.remove('Readme')
    return users
