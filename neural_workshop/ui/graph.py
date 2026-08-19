# -*- coding: utf-8 -*-
"""The progress chart: daily average and maximum score per game mode.

The chart is rebuilt into a single :class:`pyglet.graphics.Batch` and
then redrawn from that batch until something invalidates it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pyglet
from pyglet.shapes import Line

import bwaccel

from .. import state
from ..config import get_threshold_advance, get_threshold_fallback
from ..constants import PREVENT_MUSIC_SKIPPING
from ..geometry import (calc_fontsize, from_height_center, from_left_edge,
                        from_top_edge, scale_to_height, scale_to_width,
                        width_center)
from ..paths import get_data_dir, quit_with_error
from ..i18n import _

#: Column index of each field in a stats-file record.
_STATS_COLUMN: Dict[str, int] = {
    'date': 0, 'modename': 1, 'percent': 2, 'mode': 3, 'n': 4, 'ticks': 5,
    'trials': 6, 'manual': 7, 'session': 8, 'position1': 9, 'audio': 10,
    'color': 11, 'visvis': 12, 'audiovis': 13, 'arithmetic': 14, 'image': 15,
    'visaudio': 16, 'audio2': 17, 'position2': 18, 'position3': 19,
    'position4': 20, 'vis1': 21, 'vis2': 22, 'vis3': 23, 'vis4': 24,
}

#: A day with no session is plotted as a gap.
_NO_DATA: Tuple[int, int] = (-1, -1)


def _category_labels() -> Dict[str, str]:
    return {
        'position1': _('Position: '), 'position2': _('Position 2: '),
        'position3': _('Position 3: '), 'position4': _('Position 4: '),
        'vis1': _('Color/Image 1: '), 'vis2': _('Color/Image 2: '),
        'vis3': _('Color/Image 3: '), 'vis4': _('Color/Image 4: '),
        'visvis': _('Vis & nvis: '), 'visaudio': _('Vis & n-sound: '),
        'audiovis': _('Sound & n-vis: '), 'audio': _('Sound: '),
        'color': _('Color: '), 'image': _('Image: '),
        'arithmetic': _('Arithmetic: '), 'audio2': _('Sound2: '),
    }


def _pump() -> None:
    """Let the clock run mid-build so music does not skip."""
    if PREVENT_MUSIC_SKIPPING:
        pyglet.clock.tick(poll=True)


class ShapesStore:
    """Keeps drawables alive; a batch does not own a reference to them."""

    def __init__(self) -> None:
        self.s: List[Any] = []

    def __iadd__(self, other: Any) -> 'ShapesStore':
        self.s.append(other)
        return self


class Graph:
    """Score history for one game mode at a time."""

    #: How a day's sessions are collapsed into a single score.
    STYLES: Sequence[str] = ('N+10/3+4/3', 'N', '%', 'N.%', 'N+2*%-1')

    def __init__(self) -> None:
        self.graph: int = 2
        self.dictionaries: Dict[int, Dict[date, Any]] = {}
        self.percents: Dict[int, Dict[str, List[int]]] = {}
        self.reset_dictionaries()
        self.reset_percents()
        self.batch: Optional[pyglet.graphics.Batch] = None
        self.styles: List[str] = list(self.STYLES)
        self.style: int = 0
        self.sh = ShapesStore()

    # --- data ------------------------------------------------------------

    def next_style(self) -> None:
        """Cycle the day-aggregation formula and re-read the stats file."""
        self.style = (self.style + 1) % len(self.styles)
        print('style = %s' % self.styles[self.style])
        self.parse_stats()

    def reset_dictionaries(self) -> None:
        self.dictionaries = {i: {} for i in state.mode.modalities}

    def reset_percents(self) -> None:
        self.percents = {k: {i: [] for i in v}
                         for k, v in state.mode.modalities.items()}

    def next_mode(self) -> None:
        """Show the next game mode, empty or not."""
        modes = sorted(state.mode.modalities)
        index = (modes.index(self.graph) + 1) % len(modes)
        self.graph = modes[index]
        self.batch = None

    def next_nonempty_mode(self) -> None:
        """Show the next game mode that actually has recorded sessions."""
        self.next_mode()
        first = self.graph
        previous: Optional[int] = None
        while self.graph != previous and not self.dictionaries[self.graph]:
            self.next_mode()
            previous = first

    def _record_session(self, rec: Dict[str, Any]) -> None:
        """Fold one stats-file record into the per-mode dictionaries."""
        datestamp = date(rec['year'], rec['month'], rec['day'])
        if rec['hour'] < state.cfg.ROLLOVER_HOUR:
            datestamp = date.fromordinal(datestamp.toordinal() - 1)

        newmode = rec['mode']
        if newmode not in state.mode.modalities:
            return

        cats = list(rec['cats'])
        cats.extend([0] * (16 - len(cats)))
        # cats[0] is position1, which is CSV column 9; map through the index.
        column: List[Optional[int]] = [None] * 25
        column[2] = rec['percent']
        for i, value in enumerate(cats):
            column[9 + i] = value

        modalities = state.mode.modalities[newmode]
        for m in modalities:
            self.percents[newmode][m].append(int(column[_STATS_COLUMN[m]]))
        dictionary = self.dictionaries[newmode]
        dictionary.setdefault(datestamp, []).append(
            [rec['nback'], int(rec['percent'])]
            + [self.percents[newmode][n][-1] for n in modalities])

    def parse_stats(self) -> None:
        """Re-read the stats file into per-day averages and maxima."""
        self.batch = None
        self.reset_dictionaries()
        self.reset_percents()

        statsfile_path = os.path.join(get_data_dir(), state.cfg.STATSFILE)
        if not os.path.isfile(statsfile_path):
            return

        try:
            with open(statsfile_path, 'r') as statsfile:
                records = bwaccel.parse_stats_text(statsfile.read())
            for rec in records:
                if rec['manual'] != 0:  # only standard-mode sessions count
                    continue
                self._record_session(rec)
        except Exception:
            quit_with_error(
                _('Error parsing stats file\n %s') % statsfile_path,
                _('Please fix, delete or rename the stats file.'))

        advance, fallback = get_threshold_advance(), get_threshold_fallback()
        style = self.styles[self.style]
        for dictionary in self.dictionaries.values():
            for datestamp in list(dictionary):
                dictionary[datestamp] = bwaccel.aggregate_day_scores(
                    style, dictionary[datestamp], advance, fallback)

        # Append the trailing 50-session mean as the final entry.
        for game in self.percents:
            for category, pcts in self.percents[game].items():
                tail = pcts[-50:]
                pcts.append(bwaccel.mean_tail(tail, 0) if tail else 0)

    # --- drawing ---------------------------------------------------------

    def draw(self) -> None:
        if not self.batch:
            self.create_batch()
        else:
            self.batch.draw()

    def _label(self, text: str, **kwargs: Any) -> None:
        self.sh += pyglet.text.Label(text, batch=self.batch, **kwargs)

    def _line(self, x1: int, y1: int, x2: int, y2: int,
              color: Tuple[int, int, int]) -> None:
        self.sh += Line(x1, y1, x2, y2, color=color, batch=self.batch)

    def create_batch(self) -> None:
        """Build the whole chart. Long, but it is one drawing."""
        self.batch = pyglet.graphics.Batch()
        cfg = state.cfg

        linecolor = (0, 0, 255)
        linecolor2 = (255, 0, 0)
        if cfg.BLACK_BACKGROUND:
            axiscolor, minorcolor = (96, 96, 96), (64, 64, 64)
        else:
            axiscolor, minorcolor = (160, 160, 160), (224, 224, 224)
        y_marking_interval = 0.25  # in score units, so it does not scale
        x_label_width = 20

        height = int(state.window.height * 0.625)
        width = int(state.window.width * 0.625)
        center_x = width_center()
        center_y = from_height_center(20)
        left = center_x - width // 2
        right = center_x + width // 2
        top = center_y + height // 2
        bottom = center_y - height // 2

        dictionary = self.dictionaries[self.graph]
        graph_title = state.mode.long_mode_names[self.graph] + _(' N-Back')

        self._line(left, top, left, bottom, axiscolor)
        self._line(left, bottom, right, bottom, axiscolor)

        self._label(_('G: Return to Main Screen\n\nN: Next Game Type'),
                    multiline=True, width=scale_to_width(300),
                    font_size=calc_fontsize(9), color=cfg.COLOR_TEXT,
                    x=from_left_edge(10), y=from_top_edge(10),
                    anchor_x='left', anchor_y='top')
        self._label(graph_title, font_size=calc_fontsize(18), weight='bold',
                    color=cfg.COLOR_TEXT, x=center_x,
                    y=top + scale_to_height(60),
                    anchor_x='center', anchor_y='center')
        self._label(_('Date'), font_size=calc_fontsize(12), weight='bold',
                    color=cfg.COLOR_TEXT, x=center_x,
                    y=bottom - scale_to_height(80),
                    anchor_x='center', anchor_y='center')
        for text, color, offset in ((_('Maximum'), linecolor2 + (255,), 50),
                                    (_('Average'), linecolor + (255,), 25),
                                    (_('Score'), cfg.COLOR_TEXT, 0)):
            self._label(text, width=scale_to_width(1),
                        font_size=calc_fontsize(12), weight='bold',
                        color=color, x=left - scale_to_width(60),
                        y=center_y + scale_to_height(offset),
                        anchor_x='right', anchor_y='center')

        dates = sorted(dictionary)
        if len(dates) < 2:
            self._label(_('Insufficient data: two days needed'),
                        font_size=calc_fontsize(12), weight='bold',
                        color=axiscolor + (255,), x=center_x, y=center_y,
                        anchor_x='center', anchor_y='center')
            return

        ymin, ymax = self._y_range(dictionary, dates)
        _pump()

        dates = self._fill_missing_days(dictionary, dates)
        avgpoints, maxpoints = self._plot_points(
            dictionary, dates, left, bottom, width, height, ymin, ymax,
            x_label_width, cfg, minorcolor, top)
        _pump()

        self._draw_y_axis(ymin, ymax, y_marking_interval, left, right, bottom,
                          height, cfg, minorcolor)

        for points, color in ((avgpoints, linecolor), (maxpoints, linecolor2)):
            for i in range(0, len(points) - 2, 2):
                self._line(points[i], points[i + 1],
                           points[i + 2], points[i + 3], color)
        _pump()

        self._draw_legend(cfg)

    def _y_range(self, dictionary: Dict[date, Any],
                 dates: List[date]) -> Tuple[float, float]:
        """Lowest average and highest maximum, snapped to quarter points."""
        ymin, ymax = 100000.0, 0.0
        for entry in dates:
            if dictionary[entry] == _NO_DATA:
                continue
            ymin = min(ymin, dictionary[entry][0])
            ymax = max(ymax, dictionary[entry][1])
        if ymin == ymax:
            ymin = 0
        return math.floor(ymin * 4) / 4., math.ceil(ymax * 4) / 4.

    def _fill_missing_days(self, dictionary: Dict[date, Any],
                           dates: List[date]) -> List[date]:
        """Insert gap entries so the x axis is evenly spaced in days."""
        z = 0
        while z < len(dates) - 1:
            if dates[z + 1].toordinal() > dates[z].toordinal() + 1:
                newdate = date.fromordinal(dates[z].toordinal() + 1)
                dates.insert(z + 1, newdate)
                dictionary[newdate] = _NO_DATA
            z += 1
        return dates

    def _plot_points(self, dictionary: Dict[date, Any], dates: List[date],
                     left: int, bottom: int, width: int, height: int,
                     ymin: float, ymax: float, x_label_width: int,
                     cfg: Any, minorcolor: Tuple[int, int, int],
                     top: int) -> Tuple[List[int], List[int]]:
        """Screen coordinates of both series, drawing the x axis as we go."""
        avgpoints: List[int] = []
        maxpoints: List[int] = []
        xinterval = width / float(len(dates) - 1)
        skip_x = int(x_label_width // xinterval)

        for index, day in enumerate(dates):
            x = int(xinterval * index + left)
            if dictionary[day][0] != -1:
                for series, value in ((avgpoints, dictionary[day][0]),
                                      (maxpoints, dictionary[day][1])):
                    series.extend([x, int((value - ymin) / (ymax - ymin)
                                          * height + bottom)])
            if index % (skip_x + 1):
                continue
            datestring = str(day)[2:]
            # Beyond ten dates, stack the parts vertically so they fit.
            if len(dates) > 10:
                datestring = datestring.replace('-', '\n')
            self._label(datestring, multiline=True, width=scale_to_width(12),
                        font_size=calc_fontsize(8), weight='bold',
                        color=cfg.COLOR_TEXT, x=x,
                        y=bottom - scale_to_height(15),
                        anchor_x='center', anchor_y='top')
            self._line(x, bottom, x, top, minorcolor)
            self._line(x, bottom - scale_to_height(10), x, bottom, minorcolor)
        return avgpoints, maxpoints

    def _draw_y_axis(self, ymin: float, ymax: float, interval: float,
                     left: int, right: int, bottom: int, height: int,
                     cfg: Any, minorcolor: Tuple[int, int, int]) -> None:
        y_marking = ymin
        while y_marking <= ymax:
            y = int((y_marking - ymin) / (ymax - ymin) * height + bottom)
            self._label(str(round(y_marking, 2)), font_size=calc_fontsize(10),
                        weight='normal', color=cfg.COLOR_TEXT,
                        x=left - scale_to_width(30), y=y + scale_to_width(1),
                        anchor_x='center', anchor_y='center')
            self._line(left, y, right, y, minorcolor)
            self._line(left - scale_to_width(10), y, left, y, minorcolor)
            y_marking += interval

    def _draw_legend(self, cfg: Any) -> None:
        labels = _category_labels()
        modalities = state.mode.modalities[self.graph]
        parts = [_('Last 50 rounds:   ')]
        for m in modalities:
            parts.append(labels[m] + '%i%% ' % self.percents[self.graph][m][-1]
                         + ' ' * (7 - len(modalities)))
        self._label(''.join(parts), font_size=calc_fontsize(11),
                    weight='normal', color=cfg.COLOR_TEXT,
                    x=width_center(), y=scale_to_width(20),
                    anchor_x='center', anchor_y='center')
