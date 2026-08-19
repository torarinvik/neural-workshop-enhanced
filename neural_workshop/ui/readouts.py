# -*- coding: utf-8 -*-
"""Read-outs of past performance shown between sessions.

:class:`AnalysisLabel` is the important one: scoring the session that
just ended and handing the result to :class:`~neural_workshop.stats.Stats`.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import pyglet
from pyglet.window import key

import bwaccel

from .. import state
from ..config import get_threshold_advance, get_threshold_fallback
from ..constants import CLINICAL_MODE
from ..geometry import (calc_fontsize, from_bottom_edge, from_right_edge,
                        from_top_edge, scale_to_width, width_center)
from ..i18n import _

#: Every scorable modality. Arithmetic is last so it is easy to exclude.
SCORABLE_MODALITIES: Sequence[str] = (
    'position1', 'position2', 'position3', 'position4',
    'vis1', 'vis2', 'vis3', 'vis4', 'color', 'visvis', 'visaudio',
    'audiovis', 'image', 'audio', 'audio2', 'arithmetic',
)


def _percent(right: int, wrong: int) -> int:
    total = right + wrong
    return int(right * 100 / float(total)) if total else 0


class AnalysisLabel:
    """Per-modality hit/miss counts and the final score for a session."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=state.cfg.COLOR_TEXT,
            x=width_center(), y=from_bottom_edge(92),
            anchor_x='center', anchor_y='center', batch=state.batch)
        self.update()

    def _score_session(self) -> Dict[str, List[int]]:
        """Right/wrong counts per modality for the session just played."""
        cfg, mode = state.cfg, state.mode
        modalities = mode.modalities[mode.mode]
        crab = bool(mode.flags[mode.mode]['crab'])
        variable = mode.variable_list if cfg.VARIABLE_NBACK else None

        counts = {mod: [0, 0] for mod in SCORABLE_MODALITIES}
        scored = bwaccel.analyze_session(
            mode.back, crab, bool(cfg.JAEGGI_SCORING), variable,
            modalities, state.stats.session)
        for mod in modalities:
            pair = scored.get(mod)
            if pair is not None:
                counts[mod] = list(pair)
            elif mod == 'arithmetic':
                # Exact Decimal arithmetic in bwaccel; never eval().
                counts[mod] = list(bwaccel.score_arithmetic(
                    mode.back, crab, variable, state.stats.session))
        return counts

    def update(self, skip: bool = False) -> None:
        cfg, mode = state.cfg, state.mode
        if mode.started or mode.session_number == 0 or skip:
            self.label.text = ''
            return

        modalities = mode.modalities[mode.mode]
        counts = self._score_session()
        parts: List[str] = []

        if not CLINICAL_MODE:
            parts.append(_('Correct-Errors:   '))
            for mod in SCORABLE_MODALITIES[:-1]:  # arithmetic shown separately
                if mod not in modalities:
                    continue
                keytext = key.symbol_string(cfg['KEY_%s' % mod.upper()])
                if keytext == 'SEMICOLON':
                    keytext = ';'
                parts.append('%s:%i-%i   ' % (keytext, *counts[mod]))
            if 'arithmetic' in modalities:
                parts.append('%s:%i-%i   ' % (_('Arithmetic'),
                                              *counts['arithmetic']))

        # Every modality gets a column in the stats file, whether or not
        # this mode uses it; the unused ones score zero.
        category_percents = {mod: _percent(*counts[mod])
                             for mod in SCORABLE_MODALITIES}
        if cfg.JAEGGI_SCORING:
            # The protocol scores a session by its weakest modality.
            percent = min(category_percents[m] for m in modalities)
            if not CLINICAL_MODE:
                parts.append(_('Lowest score: %i%%') % percent)
        else:
            percent = _percent(sum(counts[m][0] for m in modalities),
                               sum(counts[m][1] for m in modalities))
            parts.append(_('Score: %i%%') % percent)

        self.label.text = ''.join(parts)
        state.stats.submit_session(percent, category_percents)


class ChartTitleLabel:
    """Heading above the session history chart."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(10), weight='bold',
            color=state.cfg.COLOR_TEXT, x=from_right_edge(30),
            y=from_top_edge(85), anchor_x='right', anchor_y='top',
            batch=state.batch)
        self.update()

    def update(self) -> None:
        self.label.text = '' if state.mode.started else _("Today's Last 20:")


class ChartLabel:
    """The last twenty sessions: number, mode and score."""

    ROWS = 20

    def __init__(self) -> None:
        self.start_x = from_right_edge(140)
        self.start_y = from_top_edge(105)
        self.line_spacing = calc_fontsize(15)
        self.column_spacing_12 = calc_fontsize(30)
        self.column_spacing_23 = calc_fontsize(70)
        self.font_size = calc_fontsize(10)
        self.color_normal = (128, 128, 128, 255)
        self.color_advance = (0, 160, 0, 255)
        self.color_fallback = (160, 0, 0, 255)

        offsets = (0, self.column_spacing_12,
                   self.column_spacing_12 + self.column_spacing_23)
        self.columns: List[List[pyglet.text.Label]] = [
            [pyglet.text.Label('', font_size=self.font_size,
                               x=self.start_x + offset,
                               y=self.start_y - row * self.line_spacing,
                               anchor_x='left', anchor_y='top',
                               batch=state.batch)
             for row in range(self.ROWS)]
            for offset in offsets]
        state.stats.parse_statsfile()
        self.update()

    def _row_color(self, manual: bool, percent: float) -> Sequence[int]:
        if manual:
            return self.color_normal
        if percent >= get_threshold_advance():
            return self.color_advance
        if percent < get_threshold_fallback():
            return self.color_fallback
        return self.color_normal

    def update(self) -> None:
        for column in self.columns:
            for label in column:
                label.text = ''
        if state.mode.started:
            return

        history = state.stats.history
        for index, entry in enumerate(history[-self.ROWS:]):
            session_number, mode_number, back, percent, manual = entry[:5]
            color = self._row_color(bool(manual), percent)
            for column in self.columns:
                column[index].color = color
            if manual:
                self.columns[0][index].text = 'M'
            elif session_number > -1:
                self.columns[0][index].text = '#%i' % session_number
            self.columns[1][index].text = state.mode.short_name(
                mode=mode_number, back=back)
            self.columns[2][index].text = '%i%%' % percent


class AverageLabel:
    """Rolling average score for the current mode."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(10), weight='normal',
            color=state.cfg.COLOR_TEXT, x=from_right_edge(30),
            y=from_top_edge(70), anchor_x='right', anchor_y='top',
            batch=state.batch)
        self.update()

    def update(self) -> None:
        mode = state.mode
        if mode.started or CLINICAL_MODE:
            self.label.text = ''
            return
        sessions = [s for s in state.stats.history if s[1] == mode.mode][-20:]
        average = (sum(s[2] for s in sessions) / float(len(sessions))
                   if sessions else 0.)
        self.label.text = _('%sNB average: %1.2f') % (
            mode.short_mode_names[mode.mode], average)


class TodayLabel:
    """Time and session counts for today and the last 24 hours."""

    def __init__(self) -> None:
        self.labelTitle = pyglet.text.Label(
            '', font_size=calc_fontsize(9), color=state.cfg.COLOR_TEXT,
            x=state.window.width, y=from_top_edge(5),
            anchor_x='right', anchor_y='top', width=scale_to_width(280),
            multiline=True, batch=state.batch)
        self.update()

    def update(self) -> None:
        stats = state.stats
        if state.mode.started:
            self.labelTitle.text = ''
            return
        self.labelTitle.text = _(
            '%i min %i sec done today in %i sessions\n'
            '%i min %i sec done in last 24 hours in %i sessions') % (
            stats.time_today // 60, stats.time_today % 60,
            stats.sessions_today, stats.time_thours // 60,
            stats.time_thours % 60, stats.sessions_thours)


class TrialsRemainingLabel:
    """Countdown of trials left in the running session."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(12), weight='bold',
            color=state.cfg.COLOR_TEXT, x=from_right_edge(10),
            y=from_top_edge(5), anchor_x='right', anchor_y='top',
            batch=state.batch)
        self.update()

    def update(self) -> None:
        mode = state.mode
        if not mode.started or mode.hide_text:
            self.label.text = ''
        else:
            self.label.text = _('%i remaining') % (mode.num_trials_total
                                                   - mode.trial_number)
