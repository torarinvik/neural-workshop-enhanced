# -*- coding: utf-8 -*-
"""Session history: what was played, how it scored, and what comes next.

Three layers of storage:

* ``session`` — every stimulus and every key press of the session in
  progress, which is what the scorer reads.
* ``history`` / ``full_history`` — one row per finished session, today
  and ever, read back from the stats file.
* the stats file itself, plus optional pickles for clinical logs and
  full per-session dumps.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import datetime
import os
import pickle
from datetime import date
from time import strftime
from typing import Any, Dict, List, Sequence

import bwaccel

from . import audio, runtime, state
from .config import get_threshold_advance, get_threshold_fallback
from .constants import (ATTEMPT_TO_SAVE_STATS, CLINICAL_MODE, STATS_SEPARATOR)
from .gamemode import default_nback_mode
from .paths import get_data_dir, quit_with_error
from .i18n import _

#: Stimulus streams recorded per trial, each with matching ``_input`` and
#: ``_rt`` (reaction time) streams.
_TRACKED_STIMULI: Sequence[str] = (
    'position1', 'position2', 'position3', 'position4',
    'vis1', 'vis2', 'vis3', 'vis4', 'color', 'image', 'audio', 'audio2',
)

#: Streams that have no matching stimulus of their own.
_EXTRA_STREAMS: Sequence[str] = (
    'vis', 'numbers', 'operation', 'visvis_input', 'visaudio_input',
    'audiovis_input', 'arithmetic_input', 'visvis_rt', 'visaudio_rt',
    'audiovis_rt',
)

#: Category columns of the stats file, in file order.
_CATEGORY_COLUMNS: Sequence[str] = (
    'position1', 'audio', 'color', 'visvis', 'audiovis', 'arithmetic',
    'image', 'visaudio', 'audio2', 'position2', 'position3', 'position4',
    'vis1', 'vis2', 'vis3', 'vis4',
)


class Stats:
    """Raw statistics and history. Scored by ``AnalysisLabel``."""

    def __init__(self) -> None:
        self.session: Dict[str, List[Any]] = {}
        self.initialize_session()
        self.history: List[List[Any]] = []
        self.full_history: List[List[Any]] = []  # not just today
        self.sessions_today = 0
        self.time_today = 0
        self.time_thours = 0
        self.sessions_thours = 0

    # --- the session in progress -----------------------------------------

    def initialize_session(self) -> None:
        """Start recording a fresh session."""
        self.session = {}
        for name in _TRACKED_STIMULI:
            self.session[name] = []
            self.session['%s_input' % name] = []
            self.session['%s_rt' % name] = []
        for name in _EXTRA_STREAMS:
            self.session[name] = []

    def save_input(self) -> None:
        """Append this trial's stimuli and the player's answers."""
        mode = state.mode
        for k, v in mode.current_stim.items():
            if k == 'number':
                self.session['numbers'].append(v)
            else:
                self.session[k].append(v)
            if k == 'vis':  # 'vis' also feeds the 'image' stream
                self.session['image'].append(v)
        for k, v in mode.inputs.items():
            self.session[k + '_input'].append(v)
        for k, v in mode.input_rts.items():
            self.session[k + '_rt'].append(v)
        self.session['operation'].append(mode.current_operation)
        self.session['arithmetic_input'].append(
            state.arithmetic_answer_label.parse_answer())

    # --- reading the stats file ------------------------------------------

    def clear(self) -> None:
        self.history = []
        self.sessions_today = 0
        self.time_today = 0
        self.sessions_thours = 0
        self.time_thours = 0

    def _is_today(self, datestamp: date, hour: int, today: date,
                  yesterday: date, hour_now: int) -> bool:
        """A "day" runs from ROLLOVER_HOUR to ROLLOVER_HOUR."""
        rollover = state.cfg.ROLLOVER_HOUR
        if hour_now < rollover:
            return (datestamp == today
                    or (datestamp == yesterday and hour >= rollover))
        return datestamp == today and hour >= rollover

    def parse_statsfile(self) -> None:
        """Reload today's and all-time history from the stats file."""
        self.clear()
        statsfile_path = os.path.join(get_data_dir(), state.cfg.STATSFILE)
        if not os.path.isfile(statsfile_path):
            return

        try:
            with open(statsfile_path, 'r') as statsfile:
                records = bwaccel.parse_stats_text(statsfile.read())

            today = date.today()
            yesterday = date.fromordinal(today.toordinal() - 1)
            now = datetime.datetime.today()
            hour_now = now.hour

            for rec in records:
                datestamp = date(rec['year'], rec['month'], rec['day'])
                stamp = (rec['hour'], rec['minute'], rec['second'])
                is_today = self._is_today(datestamp, rec['hour'], today,
                                          yesterday, hour_now)
                is_thours = (datestamp == today
                             or (datestamp == yesterday
                                 and stamp > (now.hour, now.minute, now.second)))

                manual = bool(rec['manual'])
                entry = [0 if manual else rec['session'], rec['mode'],
                         rec['nback'], rec['percent'], manual]
                self.full_history.append(entry)
                if is_thours:
                    self.sessions_thours += 1
                    self.time_thours += rec['sesstime']
                if is_today:
                    self.sessions_today += 1
                    self.time_today += rec['sesstime']
                    self.history.append(list(entry))
            self.retrieve_progress()
        except Exception as exc:
            runtime.debug_msg(exc)
            quit_with_error(
                _('Error parsing stats file\n%s') % statsfile_path,
                _('\nPlease fix, delete or rename the stats file.'),
                quit=False)

    def retrieve_progress(self) -> None:
        """Restore the n-back level the player last reached in this mode."""
        cfg, mode = state.cfg, state.mode
        source = self.history if cfg.RESET_LEVEL else self.full_history
        sessions = [s for s in source if s[1] == mode.mode]
        mode.enforce_standard_mode()

        if not sessions:  # nothing recorded for this user and mode
            mode.back = default_nback_mode(mode.mode)
        else:
            last = sessions[-1]
            mode.back = last[2]
            if last[3] >= get_threshold_advance():
                mode.back += 1
            mode.session_number = last[0]
            mode.progress = 0
            for s in sessions:
                if s[2] == mode.back and s[3] < get_threshold_fallback():
                    mode.progress += 1
                elif s[2] != mode.back:
                    mode.progress = 0
            if mode.progress >= cfg.THRESHOLD_FALLBACK_SESSIONS:
                mode.progress = 0
                mode.back = max(1, mode.back - 1)

        mode.num_trials_total = (mode.num_trials + mode.num_trials_factor
                                 * mode.back ** mode.num_trials_exponent)

    # --- writing a finished session --------------------------------------

    def _summary_row(self, percent: int,
                     category_percents: Dict[str, int]) -> List[str]:
        """One stats-file row for the session just finished."""
        mode = state.mode
        row = [strftime('%Y-%m-%d %H:%M:%S'), mode.short_name(), str(percent),
               str(mode.mode), str(mode.back), str(mode.ticks_per_trial),
               str(mode.num_trials_total), str(int(mode.manual)),
               str(mode.session_number)]
        row.extend(str(category_percents[name]) for name in _CATEGORY_COLUMNS)
        row.append(str(mode.ticks_per_trial * runtime.TICK_DURATION
                       * mode.num_trials_total))
        row.append(str(0))
        return row

    def _write_clinical_log(self, percent: int,
                            category_percents: Dict[str, int]) -> None:
        mode = state.mode
        record = [strftime('%Y-%m-%d %H:%M:%S'), mode.short_name(), percent,
                  mode.mode, mode.back, mode.ticks_per_trial,
                  mode.num_trials_total, int(mode.manual), mode.session_number]
        record.extend(category_percents[name] for name in _CATEGORY_COLUMNS)
        with open(os.path.join(get_data_dir(), runtime.STATS_BINARY),
                  'ab') as picklefile:
            pickle.dump(record, picklefile, protocol=2)

    def _write_session_dump(self, summary: List[str]) -> None:
        """Full per-session pickle, for later analysis."""
        cfg, mode = state.cfg, state.mode
        # FIXME: these two belong in the config, not here.
        cfg.SAVE_SESSIONS = True
        cfg.SESSION_STATS = runtime.USER + '-sessions.dat'
        if not cfg.SAVE_SESSIONS:
            return
        record = {
            'summary': summary,          # what also went into stats.txt
            'cfg': dict(cfg),
            'timestamp': strftime('%Y-%m-%d %H:%M:%S'),
            'mode': mode.mode,
            'n': mode.back,
            'manual': mode.manual,
            'trial_duration': mode.ticks_per_trial * runtime.TICK_DURATION,
            'trials': mode.num_trials_total,
            'session': self.session,
        }
        with open(os.path.join(get_data_dir(), cfg.SESSION_STATS),
                  'ab') as picklefile:
            pickle.dump(record, picklefile)

    def _save_session(self, percent: int,
                      category_percents: Dict[str, int]) -> None:
        statsfile_path = os.path.join(get_data_dir(), state.cfg.STATSFILE)
        try:
            summary = self._summary_row(percent, category_percents)
            with open(statsfile_path, 'a') as statsfile:
                statsfile.write(STATS_SEPARATOR.join(summary) + '\n')
            if CLINICAL_MODE:
                self._write_clinical_log(percent, category_percents)
            self._write_session_dump(summary)
        except Exception as exc:
            runtime.debug_msg(exc)
            quit_with_error(
                _('Error writing to stats file\n%s') % statsfile_path,
                _('\nPlease check file and directory permissions.'))

    def _apply_level_change(self, percent: int) -> None:
        """Move the n-back level up or down according to the score."""
        cfg, mode = state.cfg, state.mode
        advance = fallback = False

        if percent >= get_threshold_advance():
            mode.back += 1
            mode.progress = 0
            state.circles.update()
            if cfg.USE_APPLAUSE:
                audio.play_applause()
            advance = True
        elif mode.back > 1 and percent < get_threshold_fallback():
            if cfg.JAEGGI_MODE:
                mode.back -= 1
                fallback = True
            elif mode.progress == cfg.THRESHOLD_FALLBACK_SESSIONS - 1:
                mode.back -= 1
                mode.progress = 0
                fallback = True
                state.circles.update()
            else:
                mode.progress += 1
                state.circles.update()

        if advance or fallback:
            mode.num_trials_total = (
                mode.num_trials
                + mode.num_trials_factor * mode.back ** mode.num_trials_exponent)

        perfect = percent == 100
        awesome = not perfect and percent >= get_threshold_advance()
        great = (not (perfect or awesome)
                 and percent >= (get_threshold_advance()
                                 + get_threshold_fallback()) // 2)
        good = (not (perfect or awesome or great)
                and percent >= get_threshold_fallback())
        state.congrats_label.update(True, advance, fallback, awesome, great,
                                    good, perfect)

    def submit_session(self, percent: int,
                       category_percents: Dict[str, int]) -> None:
        """Record a finished session and react to its score."""
        mode = state.mode
        self.history.append([mode.session_number, mode.mode, mode.back,
                             percent, mode.manual])
        if ATTEMPT_TO_SAVE_STATS:
            self._save_session(percent, category_percents)
        if not mode.manual:
            self._apply_level_change(percent)
        if mode.manual and not state.cfg.USE_MUSIC_MANUAL:
            return
        if state.cfg.USE_MUSIC:
            audio.play_music(percent)
