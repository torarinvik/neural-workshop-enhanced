# -*- coding: utf-8 -*-
"""Per-task options screens.

Every workshop task owns a settings screen, reached with ``C`` from
inside the task (and from the task hub, for the highlighted task).

Most tasks describe their settings declaratively as a list of
:class:`Option` values; :class:`TaskOptions` turns that list into a
:class:`~neural_workshop.ui.menu.Menu` backed by ``cfg`` keys. The
n-back workshop is the exception: its settings screen is the much
larger :class:`~neural_workshop.ui.gameselect.GameSelect`, so the
registry points at that instead.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import (Any, Callable, Dict, NamedTuple, Optional, Sequence)

import pyglet

from .. import state
# Imported up here rather than inside a note, because the Marble Maze's
# Level row needs the ladder's *length* to build its choices. The module
# is pure arithmetic and imports no pyglet, so it costs nothing at boot.
from ..marblemaze import GRADES as _MARBLE_GRADES
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, width_center
# Imported up here rather than inside the note, because the Level row
# needs the ladder's *length* to build its choices. The module is pure
# board arithmetic and imports no pyglet, so it costs nothing at boot.
from ..go import DIFFICULTIES as _GO_LADDER
from .menu import Cycler, Menu
from ..i18n import _

#: Called after a task's options are applied, so the task can restart.
ApplyCallback = Callable[[], None]

#: Called with the rows' current values to produce a line of live text
#: shown under them. Rows are independent — each one knows nothing of
#: the others — so this is where a task explains what a *combination*
#: of them will actually do.
NoteBuilder = Callable[[Dict[str, Any]], str]


class SuffixCycler(Cycler):
    """A Cycler that renders its value with a trailing unit."""

    def __init__(self, values: Sequence[Any], default: Any = 0,
                 suffix: str = '') -> None:
        Cycler.__init__(self, values, default)
        self.suffix = suffix

    def __str__(self) -> str:
        return '%s%s' % (self.value(), self.suffix)


class UnboundedIntCycler(Cycler):
    """A positive integer selector with no highest menu value."""

    def __init__(self, value: int = 1) -> None:
        self.i = max(1, int(value))
        self.values = None

    def choose(self, val: Any) -> None:
        self.i = max(1, int(val))

    def nxt(self) -> int:
        self.i += 1
        return self.i

    def prv(self) -> int:
        self.i = max(1, self.i - 1)
        return self.i

    def value(self) -> int:
        return self.i

    def __str__(self) -> str:
        return str(self.i)


class Option(NamedTuple):
    """One row of a task's options screen.

    *key* is the ``cfg`` key the row reads and writes. *values* of
    ``None`` makes the row a Yes/No toggle; otherwise the row cycles
    through the listed choices. *default* is used when the config has
    no value, or a value outside *values*.
    """

    key: str
    label: str
    default: Any
    values: Optional[Sequence[Any]] = None
    suffix: str = ''


class TaskSpec(NamedTuple):
    """A task's settings screen: a title, its rows, and a note."""

    title: str
    options: Sequence[Option]
    #: Optional live line under the rows, rebuilt on every change.
    note: Optional[NoteBuilder] = None


#: Rows whose listed values are a ladder and not a fence: any whole
#: number from the first rung up is honoured when the config file
#: holds it, and the row then offers it among the others.
OPEN_ENDED = ('JIGSAW_PIECES', 'VIDEO_JIGSAW_PIECES')

#: The piece counts the jigsaws' rows step through.
PIECE_LADDER = (2, 4, 6, 9, 12, 16, 25, 36, 49, 64, 100, 144, 225, 400,
                625, 900, 1600, 2500)


def current_value(option: Option) -> Any:
    """Read *option* from the live config, coerced into range."""
    value = state.cfg[option.key]
    if option.key in OPEN_ENDED:
        try:
            if int(value) >= option.values[0]:
                return int(value)
        except (TypeError, ValueError):
            pass
        return option.default
    if option.key == 'NUMBEROLOGY_LEVEL':
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return int(option.default)
    if option.values is None:
        if isinstance(value, bool):
            return value
        return bool(option.default) if value is None else bool(value)
    if value in option.values:
        return value
    # Config holds junk, an old value, or nothing at all.
    if option.default in option.values:
        return option.default
    return option.values[0]


def _build_row(option: Option) -> Any:
    """The Menu value object for *option*."""
    value = current_value(option)
    if option.key == 'NUMBEROLOGY_LEVEL':
        return UnboundedIntCycler(value)
    if option.values is None:
        return bool(value)
    values = list(option.values)
    if value not in values:
        values = sorted(values + [value])
    return SuffixCycler(values, default=values.index(value),
                        suffix=option.suffix)


class TaskOptions(Menu):
    """A settings screen generated from a :class:`TaskSpec`.

    Enter writes every row back to ``cfg`` and runs *on_apply*; Escape
    leaves the config untouched.
    """

    def __init__(self, spec: TaskSpec,
                 on_apply: Optional[ApplyCallback] = None) -> None:
        self.spec = spec
        self.on_apply = on_apply
        self.applied = False
        options = [option.key for option in spec.options]
        values: Dict[str, Any] = {option.key: _build_row(option)
                                  for option in spec.options}
        names: Dict[str, str] = {option.key: option.label
                                 for option in spec.options}
        Menu.__init__(self, options, values, names=names, title=spec.title,
                      footnote=_('Esc: cancel     \u2190 \u2192 or Space: modify'
                                 ' option     Enter: apply'))

    def build_chrome(self) -> None:
        """The menu's own furniture, plus the note under it."""
        Menu.build_chrome(self)
        self.note = pyglet.text.Label(
            '', font_size=calc_fontsize(11), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(92),
            width=int(state.window.width * 0.74), multiline=True,
            align='center', anchor_x='center', anchor_y='center',
            font_name=FONTLIST)

    def update_labels(self) -> None:
        """Refill the rows, then say what they add up to.

        Menu calls this after every move and every change, so the note
        follows the rows rather than describing what they said when
        the screen opened.
        """
        Menu.update_labels(self)
        if self.spec.note is not None and getattr(self, 'note', None):
            self.note.text = self.spec.note(self.resolved())

    def resolved(self) -> Dict[str, Any]:
        """The value each row currently holds, keyed by config key."""
        result: Dict[str, Any] = {}
        for option in self.spec.options:
            value = self.values[option.key]
            result[option.key] = (value.value()
                                  if isinstance(value, Cycler) else bool(value))
        return result

    def save(self) -> None:
        for key, value in self.resolved().items():
            state.cfg[key] = value
        self.applied = True

    def close(self) -> None:
        Menu.close(self)
        if self.applied and self.on_apply is not None:
            self.on_apply()


# --- the registry ----------------------------------------------------------

MONKEY_LADDER = TaskSpec(
    title=_('Monkey Ladder options'),
    options=(
        Option('MONKEY_LADDER_GRID', _('Grid size'), 5,
               values=(3, 4, 5, 6, 7, 8, 9, 10)),
        Option('MONKEY_LADDER_START_LENGTH', _('Starting sequence length'), 3,
               values=(2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 50)),
        Option('MONKEY_LADDER_ADAPTIVE',
               _('Adapt the length to your performance'), True),
        Option('MONKEY_LADDER_SHOW_MS', _('Base display time'), 700,
               values=(200, 300, 400, 500, 700, 1000, 1500, 2000, 3000),
               suffix=' ms'),
        Option('MONKEY_LADDER_PER_TILE_MS', _('Extra display time per tile'),
               280, values=(0, 60, 120, 180, 280, 400, 600, 800),
               suffix=' ms'),
        Option('MONKEY_LADDER_REVEAL_ANSWER',
               _('Reveal the order after a miss'), True),
    ))

NCUP_MONTE = TaskSpec(
    title=_('N-Cup Monte options'),
    options=(
        Option('NCUP_MONTE_START_CUPS', _('Starting number of cups'), 3,
               values=(3, 4, 5, 6, 7, 8, 10, 12, 14, 16)),
        Option('NCUP_MONTE_MAX_CUPS', _('Maximum number of cups'), 8,
               values=(3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20)),
        Option('NCUP_MONTE_ADAPTIVE',
               _('Adapt the cup count to your performance'), True),
        Option('NCUP_MONTE_SWAPS', _('Swaps per round (plus one per cup)'), 6,
               values=(2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 100)),
        Option('NCUP_MONTE_SWAP_MS', _('Time per swap'), 340,
               values=(60, 100, 160, 220, 280, 340, 500, 750, 1000),
               suffix=' ms'),
        Option('NCUP_MONTE_REVEAL_MS', _('Time the ball stays visible'), 1150,
               values=(300, 500, 750, 1150, 1500, 2000, 3000), suffix=' ms'),
        Option('NCUP_MONTE_SHOW_CUP_NUMBERS', _('Number the cups'), True),
    ))

CONCENTRATION = TaskSpec(
    title=_('Concentration options'),
    options=(
        Option('CONCENTRATION_PAIRS', _('Pairs on the board'), 8,
               values=(4, 6, 8, 10, 12, 15, 18, 21, 24, 30, 36, 42, 50)),
        Option('CONCENTRATION_MEDIUM', _('Cards show'), 'image',
               values=('image', 'sound')),
        Option('CONCENTRATION_PEEK_MS',
               _('Reveal the board at the start for'), 0,
               values=(0, 500, 1000, 2000, 3000, 5000), suffix=' ms'),
        Option('CONCENTRATION_HIDE_MS', _('A wrong pair stays up for'), 900,
               values=(300, 500, 700, 900, 1200, 1600, 2000), suffix=' ms'),
        Option('CONCENTRATION_SHOW_TURNS', _('Count pairs and turns'), True),
    ))

RECOGNITION = TaskSpec(
    title=_('Seen it before? options'),
    options=(
        Option('RECOGNITION_TRIALS', _('Items per run'), 40,
               values=(10, 20, 30, 40, 60, 80, 100, 150, 200, 300, 500)),
        Option('RECOGNITION_MEDIUM', _('Present'), 'image',
               values=('image', 'sound')),
        Option('RECOGNITION_REPEAT_PERCENT', _('Share of items repeated'), 40,
               values=(20, 30, 40, 50), suffix='%'),
        Option('RECOGNITION_MIN_LAG', _('Smallest gap before a repeat'), 4,
               values=(1, 2, 3, 4, 6, 8, 12, 20, 30, 50, 80), suffix=' items'),
        Option('RECOGNITION_STUDY_MS', _('Hide the image after'), 0,
               values=(0, 500, 1000, 1500, 2000, 3000), suffix=' ms'),
        Option('RECOGNITION_FEEDBACK', _('Say whether each answer was right'),
               True),
    ))

REFLEX = TaskSpec(
    title=_('Reflex options'),
    options=(
        Option('REFLEX_TARGETS', _('Targets per run'), 40,
               values=(10, 20, 30, 40, 60, 80, 120, 200, 300, 500)),
        Option('REFLEX_LIFETIME_MS', _('A target takes this long to vanish'),
               1600, values=(400, 600, 800, 1200, 1600, 2200, 3000, 4000),
               suffix=' ms'),
        Option('REFLEX_SPAWN_MS', _('Gap between targets appearing'), 700,
               values=(150, 250, 400, 550, 700, 1000, 1500, 2000),
               suffix=' ms'),
        Option('REFLEX_MAX_ACTIVE', _('Most targets on screen at once'), 3,
               values=(1, 2, 3, 4, 5, 6, 8, 10, 12)),
        Option('REFLEX_SIZE', _('Size a target starts at'), 130,
               values=(60, 80, 100, 130, 170, 220, 280), suffix=' px'),
        Option('REFLEX_ADAPTIVE', _('Speed up when you hit, ease off when you miss'),
               True),
    ))

COUNTING = TaskSpec(
    title=_('Count options'),
    options=(
        Option('COUNT_SHAPE', _('Shapes to count'), 'lines',
               values=('lines', 'circles', 'triangles', 'rectangles',
                       'mixed')),
        Option('COUNT_START', _('Shapes to start with'), 8,
               values=(2, 4, 6, 8, 10, 12, 16, 20, 25, 30, 40, 50, 60)),
        Option('COUNT_TRIALS', _('Trials per run'), 15,
               values=(5, 10, 15, 20, 30, 50, 80, 100)),
        Option('COUNT_EXPOSURE_MS', _('Hide the shapes after'), 0,
               values=(0, 200, 350, 500, 750, 1000, 2000, 4000),
               suffix=' ms'),
        Option('COUNT_ADAPTIVE', _('Add a shape when right, drop one when wrong'),
               True),
        Option('COUNT_SHOW_ANSWER', _('Show the true count after each trial'),
               True),
    ))


def mr_time_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung actually demands, in its own unit.

    The rungs are shares of the interval rather than fixed windows, so
    "centiseconds" says how the error will be written and not how close
    you have to be. This is where the two are put side by side, against
    the longest gap the other rows allow — which is the row that
    decides what a share is worth.
    """
    from .mrtime import quantity, rung_at, tolerance
    number = int(chosen['MRTIME_RUNG'])
    rung = rung_at(number)
    longest = (int(chosen['MRTIME_FLASH_MS'])
               + int(chosen['MRTIME_MAX_GAP_MS'])) / 1000.
    return _('Rung %d asks for %s: within %g%% of the interval, which is '
             '%s on the longest gap these settings deal.') % (
        number, rung.unit, 100. * rung.share,
        quantity(tolerance(longest, number), number))


MR_TIME = TaskSpec(
    title=_('Mr. Time options'),
    options=(
        Option('MRTIME_MODE', _('Which half to play'), 'recall',
               values=('recall', 'produce', 'both')),
        Option('MRTIME_RUNG', _('Precision to start at'), 1,
               values=(1, 2, 3, 4, 5, 6)),
        Option('MRTIME_TRIALS', _('Trials per run'), 15,
               values=(5, 10, 15, 20, 30, 50, 80)),
        Option('MRTIME_MAX_GAP_MS', _('Longest gap before the question'),
               3000, values=(500, 1000, 2000, 3000, 5000, 8000, 15000),
               suffix=' ms'),
        Option('MRTIME_FLASH_MS', _('How long the shape stays up'), 400,
               values=(100, 200, 400, 800, 1500), suffix=' ms'),
        Option('MRTIME_ADAPTIVE',
               _('Ask for a finer unit when right, a coarser one when wrong'),
               True),
    ),
    note=mr_time_note)


def graph_mapping_note(chosen: Dict[str, Any]) -> str:
    """What this combination of rows will actually put on screen.

    Three rows decide it between them — the size, the density and
    whether mismatches keep their counts — and the third silently
    raises the first when it has to, so saying so here is the only
    place the player can see it before starting.
    """
    from .graphmapping import edge_count, subtle_floor
    density = str(chosen['GRAPH_MAP_DENSITY'])
    dots = int(chosen['GRAPH_MAP_NODES'])
    if not chosen['GRAPH_MAP_SUBTLE']:
        why = _('Mismatches will differ in their connection counts, so '
                'tallying the lines at each dot answers a pair.')
    elif dots < subtle_floor(density):
        dots = subtle_floor(density)
        why = _('No two networks smaller than %d dots share their '
                'connection counts, so runs will start there.') % dots
    else:
        why = _('Mismatches will keep every connection count, so tallying '
                'them settles nothing and the structure has to be walked.')
    return _('Each panel: %d dots, %d lines.  %s') % (
        dots, edge_count(dots, density), why)


GRAPH_MAPPING = TaskSpec(
    title=_('Graph Mapping options'),
    options=(
        Option('GRAPH_MAP_NODES', _('Dots to start with'), 6,
               values=(4, 5, 6, 7, 8, 9, 10, 12, 14, 16)),
        Option('GRAPH_MAP_DENSITY', _('How many connections'), 'medium',
               values=('sparse', 'medium', 'dense')),
        Option('GRAPH_MAP_TRIALS', _('Pairs per run'), 20,
               values=(5, 10, 15, 20, 30, 50, 80, 100)),
        Option('GRAPH_MAP_SUBTLE',
               _('Mismatches keep every connection count the same'), True),
        Option('GRAPH_MAP_EXPOSURE_MS', _('Hide the graphs after'), 0,
               values=(0, 3000, 5000, 8000, 12000, 20000), suffix=' ms'),
        Option('GRAPH_MAP_ADAPTIVE',
               _('Add a dot when right, drop one when wrong'), True),
        Option('GRAPH_MAP_FEEDBACK', _('Say whether each answer was right'),
               True),
    ),
    note=graph_mapping_note)

def matrix_reasoning_note(chosen: Dict[str, Any]) -> str:
    """What the chosen starting level actually asks.

    "Start at level 7" says nothing by itself — the levels turn
    several dials at once, and the grade table that defines them lives
    three modules away from this screen. This is the one place the
    player can see what a rung means before standing on it.
    """
    from ..ravens.matrix import GRADES
    from ..ravens.rules import SecondOrder
    level = int(chosen['RAVENS_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, level - 1))]
    grid = {2: _('two-by-two'), 3: _('three-by-three'),
            4: _('four-by-four')}[grade.across]
    if grade.active == 0:
        opening = _('Level 1 is matching: every panel of a %s grid '
                    'draws the same picture, and the question is which '
                    'of %d pieces fits.') % (grid, grade.choices)
    else:
        parts = max(len(layout.components) for layout in grade.layouts)
        carried = {
            1: _('one figure group'),
            2: _('up to two figure groups'),
            3: _('up to three figure groups'),
        }[parts]
        rules = (_('one rule') if grade.active == 1
                 else _('up to %d rules at once') % grade.active)
        opening = _('Level %d: a %s grid, %s on %s, %d answers '
                    'offered.') % (level, grid, rules, carried,
                                   grade.choices)
    hard = []
    if grade.logic:
        hard.append(_('two panels combining into a third'))
    if (grade.rules is None and grade.active
            and SecondOrder.fits(grade.sizes, grade.across)):
        hard.append(_('rules that change between rows'))
    if len(grade.sizes) > 5:
        hard.append(_('finely stepped sizes'))
    said = [opening]
    if hard:
        said.append(_('In the mix: %s.') % _(', ').join(hard))
    if chosen['RAVENS_ADAPTIVE']:
        said.append(_('From there the run moves a level with each '
                      'answer.'))
    return '  '.join(said)


MATRIX_REASONING = TaskSpec(
    title=_('Matrix Reasoning options'),
    options=(
        Option('RAVENS_LEVEL', _('Start at level'), 1,
               values=tuple(range(1, 13))),
        Option('RAVENS_TRIALS', _('Puzzles per run'), 15,
               values=(5, 10, 15, 20, 30, 50, 80, 100)),
        Option('RAVENS_EXPOSURE_MS', _('Hide the puzzle after'), 0,
               values=(0, 10000, 20000, 30000, 45000, 60000), suffix=' ms'),
        Option('RAVENS_ADAPTIVE',
               _('Go up a level when right, down when wrong'), True),
        Option('RAVENS_FEEDBACK', _('Say whether each answer was right'),
               True),
        Option('RAVENS_EXPLAIN', _('Name the rules after each answer'),
               False),
        Option('RAVENS_COLOR', _('Mix in coloured puzzles'), True),
    ),
    note=matrix_reasoning_note)

def _pieces_said(pieces: int, aspect: float, what: str) -> str:
    from .jigsaw import grid_for
    columns, rows = grid_for(pieces, aspect)
    return (_('A puzzle of %d is %d columns by %d rows: %d tiles of '
              'one %s.') % (pieces, columns, rows, columns * rows, what))


def jigsaw_note(chosen: Dict[str, Any]) -> str:
    """What the chosen grid amounts to, and whether it can be played.

    The library line matters most: the photographs are a download the
    repository does not carry, and this screen is where a player finds
    that out before a run fails to start.
    """
    from .. import datasets
    said = [_pieces_said(int(chosen['JIGSAW_PIECES']), 1.0,
                         _('photograph'))]
    if chosen['JIGSAW_ADAPTIVE']:
        said.append(_('Solve near the minimum swap count and the grid '
                      'grows; flail and it shrinks.'))
    said.append(_('Any number of pieces can be set as JIGSAW_PIECES in '
                  'the config file.'))
    stocked = datasets.have(datasets.DIV2K)
    if stocked:
        said.append(_('%d photographs downloaded.') % stocked)
    else:
        said.append(_('The photograph library is not downloaded yet — '
                      'see the Readme.'))
    return '  '.join(said)


JIGSAW = TaskSpec(
    title=_('Jigsaw Puzzle options'),
    options=(
        Option('JIGSAW_PIECES', _('Pieces'), 9, values=PIECE_LADDER),
        Option('JIGSAW_PUZZLES', _('Puzzles per run'), 3,
               values=(1, 2, 3, 5, 8, 12, 20)),
        Option('JIGSAW_ADAPTIVE',
               _('Grow the grid when you solve near the minimum'), True),
        Option('JIGSAW_PREVIEW',
               _('Show the finished picture beside the board'), True),
        Option('JIGSAW_MARK_PLACED',
               _('Outline tiles already in their place'), False),
    ),
    note=jigsaw_note)


def video_jigsaw_note(chosen: Dict[str, Any]) -> str:
    """What the chosen grid amounts to, and whether it can be played."""
    from .. import datasets, videoclips
    said = [_pieces_said(int(chosen['VIDEO_JIGSAW_PIECES']), 4 / 3.,
                         _('playing clip'))]
    if chosen['VIDEO_JIGSAW_ADAPTIVE']:
        said.append(_('Solve near the minimum swap count and the grid '
                      'grows; flail and it shrinks.'))
    said.append(_('Any number of pieces can be set as '
                  'VIDEO_JIGSAW_PIECES in the config file.'))
    stocked = datasets.have(datasets.UCF101)
    if stocked:
        said.append(_('%d clips downloaded.') % stocked)
    else:
        said.append(_('The video library is not downloaded yet — '
                      'see the Readme.'))
    if not videoclips.have_ffmpeg():
        said.append(_('The ffmpeg program was not found.'))
    return '  '.join(said)


VIDEO_JIGSAW = TaskSpec(
    title=_('Video Jigsaw options'),
    options=(
        Option('VIDEO_JIGSAW_PIECES', _('Pieces'), 6, values=PIECE_LADDER),
        Option('VIDEO_JIGSAW_PUZZLES', _('Clips per run'), 3,
               values=(1, 2, 3, 5, 8, 12, 20)),
        Option('VIDEO_JIGSAW_ADAPTIVE',
               _('Grow the grid when you solve near the minimum'), True),
        Option('VIDEO_JIGSAW_PREVIEW',
               _('Show the whole clip playing beside the board'), False),
        Option('VIDEO_JIGSAW_MARK_PLACED',
               _('Outline tiles already in their place'), False),
    ),
    note=video_jigsaw_note)


def video_sequence_note(chosen: Dict[str, Any]) -> str:
    """What the chosen cut amounts to, and whether it can be played."""
    from .. import datasets, videoclips
    pieces = int(chosen['VIDEO_SEQUENCE_PIECES'])
    said = [_('Each clip is cut into %d stretches of time.') % pieces]
    if chosen['VIDEO_SEQUENCE_ADAPTIVE']:
        said.append(_('Solve near the minimum swap count and the next '
                      'clip has one piece more; flail and one fewer.'))
    stocked = datasets.have(datasets.UCF101)
    if stocked:
        said.append(_('%d clips downloaded.') % stocked)
    else:
        said.append(_('The video library is not downloaded yet — '
                      'see the Readme.'))
    if not videoclips.have_ffmpeg():
        said.append(_('The ffmpeg program was not found.'))
    return '  '.join(said)


VIDEO_SEQUENCE = TaskSpec(
    title=_('Video Sequence options'),
    options=(
        Option('VIDEO_SEQUENCE_PIECES', _('Pieces per clip'), 4,
               values=(3, 4, 5, 6, 7, 8, 9)),
        Option('VIDEO_SEQUENCE_PUZZLES', _('Clips per run'), 5,
               values=(1, 3, 5, 8, 12, 20)),
        Option('VIDEO_SEQUENCE_ADAPTIVE',
               _('Add a piece when you solve near the minimum'), True),
        Option('VIDEO_SEQUENCE_MARK_PLACED',
               _('Outline pieces already in their place'), False),
    ),
    note=video_sequence_note)


def camera_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung asks for."""
    from .. import camera
    level = camera.grade(int(chosen['CAMERA_RUNG']))
    reach = level.reach
    said = [_('Rung %d: within %s and %.2g degrees, %d objects.')
            % (level.rung, ('%.2g m' % reach) if reach >= 0.01
               else ('%.2g mm' % (reach * 1000)), level.aim,
               level.objects)]
    if level.meter:
        said.append(_('A meter shows how close you are.'))
    if chosen['CAMERA_ADAPTIVE']:
        said.append(_('A match climbs a rung, a miss drops one; the '
                      'ladder has no top.'))
    return '  '.join(said)


CAMERA = TaskSpec(
    title=_('Camera options'),
    options=(
        Option('CAMERA_RUNG', _('Starting rung'), 1,
               values=(1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40,
                       60, 100)),
        Option('CAMERA_TRIALS', _('Photographs per run'), 8,
               values=(1, 3, 5, 8, 12, 20, 30)),
        Option('CAMERA_ADAPTIVE',
               _('Climb a rung on a match, drop one on a miss'), True),
    ),
    note=camera_note)


def sonar_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung adds to the decisions."""
    from .. import sonar
    level = sonar.grade(int(chosen['SONAR_RUNG']))
    said = [_('Rung %d: a %dx%d grid, a wrong dig costs %d pings.')
            % (level.rung, level.side, level.side, level.penalty)]
    if level.noise:
        said.append(_('%d%% of readings are off by one band.')
                    % round(level.noise * 100))
    if level.drift:
        said.append(_('The target drifts.'))
    if level.slack < 0:
        said.append(_('You must beat the reference player.'))
    return '  '.join(said)


SONAR = TaskSpec(
    title=_('Sonar options'),
    options=(
        Option('SONAR_RUNG', _('Starting rung'), 1,
               values=(1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30)),
        Option('SONAR_TRIALS', _('Rounds per run'), 8,
               values=(1, 3, 5, 8, 12, 20)),
        Option('SONAR_ADAPTIVE',
               _('Climb a rung under par, drop one over'), True),
    ),
    note=sonar_note)


def hidden_rule_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung allows the rule to be."""
    from .. import hiddenrule
    level = hiddenrule.grade(int(chosen['HIDDEN_RULE_RUNG']))
    said = [_('Rung %d: %d properties, a wrong answer costs %d tests.')
            % (level.rung, len(level.values), level.penalty)]
    kinds = {'both': _('and'), 'either': _('or'),
             'one_of': _('one but not both'), 'all': _('three at once')}
    named = [kinds[form] for form in level.forms if form in kinds]
    if level.nots:
        named.append(_('not'))
    if 'two_of' in level.forms:
        named.append(_('mixtures'))
    if named:
        said.append(_('Rules may use: %s.') % ', '.join(named))
    if level.noise:
        said.append(_('The lamp lies on %d%% of tests.')
                    % round(level.noise * 100))
    if level.factor < 1.0:
        said.append(_('You must beat the reference player.'))
    return '  '.join(said)


HIDDEN_RULE = TaskSpec(
    title=_('Hidden Rule options'),
    options=(
        Option('HIDDEN_RULE_RUNG', _('Starting rung'), 1,
               values=(1, 2, 3, 4, 6, 8, 10, 12, 13, 16, 19, 25, 30)),
        Option('HIDDEN_RULE_TRIALS', _('Rounds per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('HIDDEN_RULE_ADAPTIVE',
               _('Climb a rung under par, drop one over'), True),
    ),
    note=hidden_rule_note)


def desktop_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung puts on the screen."""
    from .. import desktop
    level = desktop.grade(int(chosen['DESKTOP_RUNG']))
    said = [_('Rung %d: %d window(s), %d setting(s) to reach.')
            % (level.rung, level.windows, level.goals)]
    found = []
    if level.tabs > 1:
        found.append(_('tabs'))
    if level.rows < level.per_tab:
        found.append(_('scrolling'))
    if level.dialogs:
        found.append(_('menus and dialogs'))
    if level.windows > 1:
        found.append(_('overlapping windows'))
    if level.depends:
        found.append(_('greyed-out controls'))
    if level.applies:
        found.append(_('Apply buttons'))
    if level.popups:
        found.append(_('popups'))
    if level.minimised:
        found.append(_('minimised windows'))
    if level.notes:
        found.append(_('sticky notes'))
    if level.offscreen:
        found.append(_('a window off the screen'))
    if level.closed:
        found.append(_('closed windows'))
    if level.submenus:
        found.append(_('submenus'))
    if level.explorer:
        found.append(_('a file explorer with %d file(s) to move')
                     % level.moves)
    if level.ex_tabs > 1:
        found.append(_('explorer tabs'))
    if level.deletes:
        found.append(_('deleting'))
    if level.explorer_closed:
        found.append(_('the explorer closed'))
    if level.restores:
        found.append(_('restoring from the Trash'))
    if level.copies:
        found.append(_('copying'))
    if level.list_view:
        found.append(_('list views'))
    if level.hide_card:
        found.append(_('a card that hides'))
    if found:
        said.append(_('With %s.') % ', '.join(found))
    if level.factor < 1.0:
        said.append(_('You must beat the reference.'))
    return '  '.join(said)


def gamble_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung puts out."""
    from .. import gamble
    level = gamble.grade(int(chosen['GAMBLE_RUNG']))
    said = [_('Rung %d: %d machines, %d pulls.')
            % (level.rung, level.arms, level.pulls)]
    found = []
    if level.drift:
        found.append(_('odds that drift'))
    if level.biters:
        found.append(_('machines that bite'))
    if level.jumps:
        found.append(_('odds that jump'))
    if level.price:
        found.append(_('pulls that cost, a bankroll and Stop'))
    if found:
        said.append(_('With %s.') % ', '.join(found))
    if level.allow < 0:
        said.append(_('You must beat the reference.'))
    return '  '.join(said)


GAMBLE = TaskSpec(
    title=_('Gamble options'),
    options=(
        Option('GAMBLE_RUNG', _('Starting rung'), 1,
               values=(1, 3, 6, 10, 14, 18, 21, 25, 30)),
        Option('GAMBLE_TRIALS', _('Rounds per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('GAMBLE_ADAPTIVE',
               _('Climb a rung at par, drop one under'), True),
    ),
    note=gamble_note)


def triage_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung puts on the table."""
    from .. import triage
    level = triage.grade(int(chosen['TRIAGE_RUNG']))
    said = [_('Rung %d: %d cards of %d to %d digits; the moves cover '
              'about %d%% of the work.')
            % (level.rung, level.cards, level.shortest, level.longest,
               min(100, int(round(level.tight * 100))))]
    found = []
    if level.traps:
        found.append(_('pay that does not follow cost'))
    if level.hidden:
        found.append(_('face-down cards that cost a move to turn'))
    if found:
        said.append(_('With %s.') % ', '.join(found))
    if level.rung > 20:
        said.append(_('You must beat the reference.'))
    return '  '.join(said)


TRIAGE = TaskSpec(
    title=_('Triage options'),
    options=(
        Option('TRIAGE_RUNG', _('Starting rung'), 1,
               values=(1, 3, 5, 8, 12, 16, 20, 21, 25, 30)),
        Option('TRIAGE_TRIALS', _('Rounds per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('TRIAGE_ADAPTIVE',
               _('Climb a rung at par, drop one under'), True),
    ),
    note=triage_note)


def what_next_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung shows, and whether it can be played."""
    from .. import datasets, videoclips, whatnext
    level = whatnext.grade(int(chosen['WHAT_NEXT_RUNG']))
    kinds = [whatnext.describe(k) for k in level.kinds]
    said = [_('Rung %d: %d options; the decoys are %s.')
            % (level.rung, level.choices, ', '.join(kinds))]
    if level.context < 1.0:
        said.append(_('Only the last %d%% of the opening is shown.')
                    % int(round(level.context * 100)))
    stocked = datasets.have(datasets.UCF101)
    if stocked:
        said.append(_('%d clips downloaded.') % stocked)
    else:
        said.append(_('The video library is not downloaded yet — '
                      'see the Readme.'))
    if not videoclips.have_ffmpeg():
        said.append(_('The ffmpeg program was not found.'))
    return '  '.join(said)


WHAT_NEXT = TaskSpec(
    title=_('What Happens Next options'),
    options=(
        Option('WHAT_NEXT_RUNG', _('Starting rung'), 1,
               values=(1, 4, 8, 12, 16, 20, 24, 30)),
        Option('WHAT_NEXT_TRIALS', _('Clips per run'), 10,
               values=(1, 5, 10, 20, 40)),
        Option('WHAT_NEXT_ADAPTIVE',
               _('Climb a rung when right, drop one when wrong'), True),
    ),
    note=what_next_note)


def manual_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung's panel and procedure hold."""
    from .. import manual
    level = manual.grade(int(chosen['MANUAL_RUNG']))
    said = [_('Rung %d: %d steps on a panel of %d switches, %d knobs, '
              '%d buttons and %d lamps.')
            % (level.rung, level.steps, level.switches, level.knobs,
               level.buttons, level.lamps)]
    words = {'if': _('steps that depend on a lamp'),
             'count': _('counts read off the display'),
             'copy': _('copying one control to another'),
             'until': _('pressing until a lamp changes'),
             'recall': _('putting controls back as they started'),
             'skip': _('steps that skip the next')}
    found = [words[k] for k in level.kinds if k in words]
    if level.shuffled:
        found.append(_('controls in shuffled order'))
    if found:
        said.append(_('With %s.') % ', '.join(found))
    return '  '.join(said)


MANUAL = TaskSpec(
    title=_('Manual options'),
    options=(
        Option('MANUAL_RUNG', _('Starting rung'), 1,
               values=(1, 2, 5, 9, 13, 17, 20, 25, 30)),
        Option('MANUAL_TRIALS', _('Procedures per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('MANUAL_ADAPTIVE',
               _('Climb a rung when right, drop one when wrong'), True),
    ),
    note=manual_note)


def notebook_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung asks to be remembered."""
    from .. import notebook
    level = notebook.grade(int(chosen['NOTEBOOK_RUNG']))
    said = [_('Rung %d: %d codes, up to %d waiting at once, at least %d '
              'cards before each is asked; %d notebook lines.')
            % (level.rung, level.facts, level.hold, level.gap + 1,
               level.lines)]
    found = []
    if level.noise:
        found.append(_('cards not needed'))
    if level.updates:
        found.append(_('codes that change'))
    if found:
        said.append(_('With %s.') % ', '.join(found))
    if level.lines < level.hold:
        said.append(_('Some will have to be kept in your head.'))
    return '  '.join(said)


NOTEBOOK = TaskSpec(
    title=_('Notebook options'),
    options=(
        Option('NOTEBOOK_RUNG', _('Starting rung'), 1,
               values=(1, 3, 6, 8, 12, 16, 20, 25, 30)),
        Option('NOTEBOOK_TRIALS', _('Rounds per run'), 3,
               values=(1, 3, 5, 8)),
        Option('NOTEBOOK_ADAPTIVE',
               _('Climb a rung when all right, drop one otherwise'), True),
    ),
    note=notebook_note)


def browser_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung's shop and shopping list hold."""
    from .. import browser
    level = browser.grade(int(chosen['BROWSER_RUNG']))
    said = [_('Rung %d: %d departments of %d products; %d to buy.')
            % (level.rung, level.departments, level.products, level.buys)]
    found = []
    if level.sorting:
        found.append(_('sortable lists'))
    if level.stock:
        found.append(_('stock shown only on product pages'))
    if level.shipping:
        found.append(_('shipping costs'))
    if level.paged:
        found.append(_('lists over several pages'))
    if level.stale:
        found.append(_('list prices that may be out of date'))
    if found:
        said.append(_('With %s.') % ', '.join(found))
    said.append(_('Par allows %d%% of a thorough shopper\'s extra clicks.')
                % int(round(level.slack * 100)))
    return '  '.join(said)


BROWSER = TaskSpec(
    title=_('Browser options'),
    options=(
        Option('BROWSER_RUNG', _('Starting rung'), 1,
               values=(1, 3, 6, 9, 12, 15, 18, 21, 25, 30)),
        Option('BROWSER_TRIALS', _('Shopping trips per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('BROWSER_ADAPTIVE',
               _('Climb a rung at par, drop one under'), True),
    ),
    note=browser_note)


def wiring_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung wires up."""
    from .. import wiring
    level = wiring.grade(int(chosen['WIRING_RUNG']))
    said = [_('Rung %d: %d switches, %d lamps, a wrong answer costs %d.')
            % (level.rung, level.switches, level.lamps, level.penalty)]
    gates = {'and': _('and / or'), 'xor': _('xor'),
             'three': _('three-input gates')}
    named = [gates[g] for g in level.gates if g in gates]
    if level.inverts:
        named.append(_('inverted inputs'))
    if named:
        said.append(_('Gates: %s.') % ', '.join(named))
    if level.noise:
        said.append(_('A lamp lies on %d%% of looks.')
                    % round(level.noise * 100))
    if level.factor < 1.0:
        said.append(_('You must beat the reference.'))
    return '  '.join(said)


WIRING = TaskSpec(
    title=_('Hidden Wiring options'),
    options=(
        Option('WIRING_RUNG', _('Starting rung'), 1,
               values=(1, 3, 5, 7, 10, 12, 16, 20, 25, 30)),
        Option('WIRING_TRIALS', _('Rounds per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('WIRING_ADAPTIVE',
               _('Climb a rung under par, drop one over'), True),
    ),
    note=wiring_note)


def forms_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung's form asks."""
    from .. import forms
    level = forms.grade(int(chosen['FORMS_RUNG']))
    said = [_('Rung %d: up to %d fields on %d page(s).')
            % (level.rung, level.fields, level.pages)]
    kinds = {'date': _('dates to reformat'), 'digits': _('phone numbers'),
             'choice': _('lists that complete'),
             'radio': _('checkboxes and radio buttons')}
    named = [kinds[k] for k in level.kinds if k in kinds]
    if level.conditional:
        named.append(_('fields that appear'))
    if level.letter:
        named.append(_('a letter to read'))
    if level.decoys:
        named.append(_("other people's details"))
    if named:
        said.append(_('With %s.') % ', '.join(named))
    if level.factor <= 1.0:
        said.append(_('Par is the reference typist exactly.'))
    return '  '.join(said)


FORMS = TaskSpec(
    title=_('Forms options'),
    options=(
        Option('FORMS_RUNG', _('Starting rung'), 1,
               values=(1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 25)),
        Option('FORMS_TRIALS', _('Rounds per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('FORMS_ADAPTIVE',
               _('Climb a rung under par, drop one over'), True),
    ),
    note=forms_note)


def bluff_note(chosen: Dict[str, Any]) -> str:
    """Who the starting rung puts across the table."""
    from .. import bluff
    level = bluff.grade(int(chosen['BLUFF_RUNG']))
    names = {'station': _('a calling station'), 'rock': _('a rock'),
             'maniac': _('a maniac'), 'sound': _('a sound player'),
             'adaptive': _('a player who adapts to you')}
    who = [names[k] for k in level.kinds]
    said = [_('Rung %d: %d hands, cards 1 to %d.')
            % (level.rung, level.hands, level.cards)]
    if len(who) == 1:
        said.append(_('Against %s.') % who[0])
    else:
        said.append(_('Against one of: %s.') % ', '.join(who))
    if level.changes:
        said.append(_('It changes partway.'))
    if level.allow < 0:
        said.append(_('You must beat the reference.'))
    return '  '.join(said)


BLUFF = TaskSpec(
    title=_('Bluff options'),
    options=(
        Option('BLUFF_RUNG', _('Starting rung'), 1,
               values=(1, 3, 5, 7, 10, 14, 18, 21, 25)),
        Option('BLUFF_TRIALS', _('Rounds per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('BLUFF_ADAPTIVE',
               _('Climb a rung at par, drop one under'), True),
    ),
    note=bluff_note)


DESKTOP = TaskSpec(
    title=_('Desktop options'),
    options=(
        Option('DESKTOP_RUNG', _('Starting rung'), 1,
               values=(1, 2, 3, 4, 5, 6, 8, 11, 13, 15, 16, 18, 20, 25,
                       30)),
        Option('DESKTOP_TRIALS', _('Rounds per run'), 5,
               values=(1, 3, 5, 8, 12)),
        Option('DESKTOP_ADAPTIVE',
               _('Climb a rung under par, drop one over'), True),
    ),
    note=desktop_note)


def dispatch_note(chosen: Dict[str, Any]) -> str:
    """What the starting rung puts on the map."""
    from .. import dispatch
    level = dispatch.grade(int(chosen['DISPATCH_RUNG']))
    said = [_('Rung %d: %d crews, bursts of up to %d.')
            % (level.rung, level.crews, level.burst)]
    if level.scout:
        said.append(_('%d%% of reports are false alarms; a scout can '
                      'check.') % round(level.false_rate * 100))
    if level.error:
        said.append(_('Reported sizes are off by up to %d%%.')
                    % round(level.error * 100))
    if level.refit:
        said.append(_('A crew can stand %d seconds at a station for a '
                      'refit and work twice as fast after.')
                    % round(level.refit))
    if level.factor < 1.0:
        said.append(_('You must do better than the reference dispatcher.'))
    return '  '.join(said)


DISPATCH = TaskSpec(
    title=_('Dispatch options'),
    options=(
        Option('DISPATCH_RUNG', _('Starting rung'), 1,
               values=(1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30)),
        Option('DISPATCH_TRIALS', _('Rounds per run'), 3,
               values=(1, 2, 3, 5, 8)),
        Option('DISPATCH_ADAPTIVE',
               _('Climb a rung under par, drop one over'), True),
    ),
    note=dispatch_note)


def hanoi_note(chosen: Dict[str, Any]) -> str:
    """The minimum, spelled out — 2^n - 1 grows faster than a row of
    numbers suggests, and the difference between five disks and eight
    is the difference between 31 moves and 255."""
    disks = int(chosen['HANOI_DISKS'])
    said = [_('A tower of %d disks moves in %d moves at minimum.')
            % (disks, (1 << disks) - 1)]
    if chosen['HANOI_ADAPTIVE']:
        said.append(_('Solve near that and the next tower is taller; '
                      'wander and it shrinks.'))
    return '  '.join(said)


HANOI = TaskSpec(
    title=_('Tower of Hanoi options'),
    options=(
        Option('HANOI_DISKS', _('Disks to start with'), 4,
               values=(3, 4, 5, 6, 7, 8, 9, 10, 11, 12)),
        Option('HANOI_ROUNDS', _('Towers per run'), 3,
               values=(1, 2, 3, 5, 8, 10)),
        Option('HANOI_ADAPTIVE',
               _('Grow the tower when you solve near the minimum'), True),
    ),
    note=hanoi_note)


def tracking_note(chosen: Dict[str, Any]) -> str:
    """What the chosen flock adds up to, and the one silent clamp.

    Targets are clamped to one fewer than the balls — a trial where
    every ball is a target answers itself — and the clamp is silent
    in play, so this is where the player learns their numbers were
    bent before a run quietly uses different ones.
    """
    balls = int(chosen['TRACK_BALLS'])
    asked = int(chosen['TRACK_TARGETS'])
    said = []
    if asked > balls - 1:
        said.append(_('With %d balls at most %d can be targets, so runs '
                      'will track %d.') % (balls, balls - 1, balls - 1))
        asked = balls - 1
    said.insert(0, _('%d balls bounce for %d seconds; %d of them are '
                     'yours to follow.') % (balls, int(chosen['TRACK_SECONDS']),
                                            asked))
    if chosen['TRACK_ADAPTIVE']:
        said.append(_('Catch them all and the next round asks for one '
                      'more; miss and it asks for one fewer.'))
    return '  '.join(said)


TRACKING = TaskSpec(
    title=_('Moving Targets options'),
    options=(
        Option('TRACK_BALLS', _('Balls on screen'), 8,
               values=(3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30)),
        Option('TRACK_TARGETS', _('Balls to track'), 2,
               values=(1, 2, 3, 4, 5, 6, 8, 10, 12, 15)),
        Option('TRACK_SECONDS', _('Seconds of motion'), 8,
               values=(3, 5, 8, 10, 15, 20, 30, 45, 60), suffix=' s'),
        Option('TRACK_SPEED', _('Ball speed'), 16,
               values=(8, 12, 16, 22, 30, 40, 55, 75)),
        Option('TRACK_ROUNDS', _('Rounds per run'), 5,
               values=(3, 5, 8, 10, 15, 20, 30, 50)),
        Option('TRACK_ADAPTIVE',
               _('Ask for one more target when you catch them all'), True),
    ),
    note=tracking_note)


def lookout_note(chosen: Dict[str, Any]) -> str:
    """Why the channel choice is the difficulty dial, said at the dial.

    One channel is a single search — a colour "pops out", the eye
    finds it in parallel, and a shape is only a little slower. Both
    at once is divided attention: two independent signals through one
    churn, each with its own key, and that is the hard setting.
    """
    kind = str(chosen['LOOKOUT_CUE'])
    what = {
        'color': _('One key (J): press when anything matches the '
                   "glyph's colour. Colour \"pops out\" — the easiest "
                   'search.'),
        'form': _('One key (F): press when anything matches the '
                  "glyph's shape, whatever its colour — found a "
                  'little slower than a colour.'),
        'both': _('Two keys: F when the shape is on screen, J when '
                  'the colour is. Two independent signals at once — '
                  'the hard setting.'),
    }.get(kind, '')
    said = [_('%d shapes drift and change; the HUD glyph is what to '
              'watch for.') % int(chosen['LOOKOUT_SHAPES']), what]
    if chosen['LOOKOUT_ADAPTIVE']:
        said.append(_('A hit adds a shape; a miss or a false alarm '
                      'takes one away.'))
    return '  '.join(said)


LOOKOUT = TaskSpec(
    title=_('Lookout options'),
    options=(
        Option('LOOKOUT_SHAPES', _('Shapes on screen'), 8,
               values=(3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30)),
        Option('LOOKOUT_CUE', _('Watch the glyph for its'), 'color',
               values=('color', 'form', 'both')),
        Option('LOOKOUT_SPEED', _('Drift speed'), 16,
               values=(8, 12, 16, 22, 30, 40, 55, 75)),
        Option('LOOKOUT_MORPH_MS', _('A shape changes about every'), 2000,
               values=(800, 1200, 2000, 3000, 5000, 8000), suffix=' ms'),
        Option('LOOKOUT_CUES', _('Cues per run'), 10,
               values=(5, 10, 15, 20, 30, 50)),
        Option('LOOKOUT_ADAPTIVE',
               _('Add a shape on a hit, drop one on a mistake'), True),
    ),
    note=lookout_note)


def pursuit_note(chosen: Dict[str, Any]) -> str:
    """The chosen quarry in one line, and what the dials trade.

    Six independent axes make a wide space; the note names the two
    that matter most at a glance — how fast, how unpredictable — and
    says when an axis is switched off entirely.
    """
    speed = int(chosen['PURSUIT_SPEED'])
    gap = int(chosen['PURSUIT_TURN_MS'])
    said = [_('The shape covers about %d%% of the screen a second and '
              'breaks direction every %.1f s or so, up to %d degrees '
              'at a time.') % (speed, gap / 1000.,
                               int(chosen['PURSUIT_TURN_DEGREES']))]
    still = []
    if not int(chosen['PURSUIT_SURGE']):
        still.append(_('steady pace'))
    if not int(chosen['PURSUIT_SIZE_WOBBLE']):
        still.append(_('fixed size'))
    if not int(chosen['PURSUIT_MORPH_MS']):
        still.append(_('fixed shape'))
    if still:
        said.append(_('Switched off: %s.') % _(', ').join(still))
    if chosen['PURSUIT_ADAPTIVE']:
        said.append(_('Hold on 70%% of a round and everything speeds '
                      'up 5%%; drop under 40%% and it eases 5%%.'))
    return '  '.join(said)


PURSUIT = TaskSpec(
    title=_('Pursuit options'),
    options=(
        Option('PURSUIT_SPEED', _('Base speed'), 18,
               values=(4, 6, 8, 10, 12, 14, 16, 18, 20, 25, 30, 35, 40,
                       50, 60, 75, 90)),
        Option('PURSUIT_SURGE', _('Speed surges up to'), 60,
               values=(0, 20, 40, 60, 80, 100, 150, 200, 300),
               suffix='%'),
        Option('PURSUIT_TURN_MS', _('Direction breaks about every'), 900,
               values=(200, 300, 400, 600, 900, 1200, 1600, 2200, 3000,
                       5000), suffix=' ms'),
        Option('PURSUIT_TURN_DEGREES', _('Sharpest break'), 120,
               values=(30, 45, 60, 90, 120, 150, 180)),
        Option('PURSUIT_SIZE', _('Base size'), 22,
               values=(10, 13, 16, 19, 22, 26, 31, 38, 46, 60)),
        Option('PURSUIT_SIZE_WOBBLE', _('Size wobbles up to'), 40,
               values=(0, 15, 30, 40, 55, 70, 85), suffix='%'),
        Option('PURSUIT_MORPH_MS', _('Shape shifts about every'), 2000,
               values=(0, 500, 900, 1400, 2000, 3000, 5000),
               suffix=' ms'),
        Option('PURSUIT_SECONDS', _('Seconds per round'), 20,
               values=(10, 15, 20, 30, 45, 60, 90, 120), suffix=' s'),
        Option('PURSUIT_ROUNDS', _('Rounds per run'), 3,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('PURSUIT_ADAPTIVE',
               _('Tighten the screws while you hold on'), True),
    ),
    note=pursuit_note)


def out_of_sight_note(chosen: Dict[str, Any]) -> str:
    """What the chosen field hides, and the one silent clamp.

    Two of these rows can switch a whole half of the task off — no
    crossings, or no slabs — and between them they are what makes a
    single frame too little to answer from, so a run without either
    is a much easier game than the name promises. The note says so at
    the dial rather than leaving it to be discovered.
    """
    dots = int(chosen['SIGHT_DOTS'])
    yours = int(chosen['SIGHT_TARGETS'])
    said = []
    if yours > dots - 1:
        said.append(_('With %d dots at most %d can be yours, so runs '
                      'will hold %d.') % (dots, dots - 1, dots - 1))
        yours = dots - 1
    said.insert(0, _('%d dots drift and %d of them are yours to hold.')
                % (dots, yours))
    gap = int(chosen['SIGHT_CROSS_MS'])
    slabs = int(chosen['SIGHT_BLINDS'])
    if gap:
        said.append(_('Two of them meet and pass through each other '
                      'every %.1f s or so.') % (gap / 1000.))
    if slabs:
        said.append(_('Up to %d slabs hide whatever goes behind them '
                      '— however many of that width fit without '
                      'taking half the field.') % slabs)
    if not gap and not slabs:
        said.append(_('With no crossings and no slabs nothing is ever '
                      'in doubt — the dots can simply be watched.'))
    said.append(_('%d questions a round, asked while everything keeps '
                  'moving.') % int(chosen['SIGHT_PROBES']))
    if chosen['SIGHT_ADAPTIVE']:
        said.append(_('A round answered whole asks for one more dot; '
                      'a mistake asks for one fewer.'))
    return '  '.join(said)


OUT_OF_SIGHT = TaskSpec(
    title=_('Out of Sight options'),
    options=(
        Option('SIGHT_DOTS', _('Dots on screen'), 8,
               values=(3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30)),
        Option('SIGHT_TARGETS', _('Dots to hold'), 2,
               values=(1, 2, 3, 4, 5, 6, 8, 10, 12, 15)),
        Option('SIGHT_SPEED', _('Dot speed'), 16,
               values=(8, 12, 16, 22, 30, 40, 55, 75)),
        Option('SIGHT_CROSS_MS', _('Two dots cross about every'), 1600,
               values=(0, 600, 900, 1200, 1600, 2200, 3000, 5000),
               suffix=' ms'),
        Option('SIGHT_BLINDS', _('Slabs to hide behind'), 3,
               values=(0, 1, 2, 3, 4, 5, 6, 8)),
        Option('SIGHT_BLIND_WIDTH', _('How wide a slab is'), 9,
               values=(4, 6, 9, 12, 16, 20), suffix='%'),
        Option('SIGHT_PROBES', _('Questions per round'), 6,
               values=(2, 4, 6, 8, 10, 15, 20)),
        Option('SIGHT_ROUNDS', _('Rounds per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('SIGHT_ADAPTIVE',
               _('Hold one more dot when a round comes back whole'), True),
    ),
    note=out_of_sight_note)


def buzz_wire_note(chosen: Dict[str, Any]) -> str:
    """What this rung's wire, hand and clock actually amount to.

    Every number here is read off the grade rather than described in
    round terms, because the whole of this task is one quantity — how
    much room there is between the wire and the hole — and a player who
    cannot see that number has no way to tell the third rung from the
    ninth until they have lost on it.
    """
    from ..buzzwire import (GRADES, WIRE_RADIUS, clamped_rung, clearance,
                            hand_speed, ticks_per_clearance)
    rung = clamped_rung(int(chosen['BUZZ_LEVEL']))
    grade = GRADES[rung - 1]
    said = [_('Level %d, "%s". The loop\'s hole is %.0f mm across against a '
              '%.0f mm wire, so you have %.1f mm of room on either side, and '
              'one full press of a key eventually uses about %d%% of it.')
            % (rung, _(grade.name), grade.hole * 20.0, WIRE_RADIUS * 20.0,
               clearance(grade) * 10.0,
               int(round(100.0 / max(1e-6, ticks_per_clearance(grade)))))]
    said.append(
        _('The hand travels %.1f cm a second flat out and the clock allows '
          '%d seconds.') % (hand_speed(grade), int(grade.seconds))
        if not grade.sag else
        _('The hand travels %.1f cm a second flat out, sags at %.0f cm/s² '
          'when you stop holding it up, and the clock allows %d seconds.')
        % (hand_speed(grade), grade.sag, int(grade.seconds)))
    if grade.tremor:
        said.append(_('It also shakes: a drift that turns over about %d '
                      'times a second, which you have to catch rather '
                      'than wait out.') % max(1, int(1.0 / grade.tremor_tau)))
    if grade.twist > 0.0:
        said.append(_('From this rung the loop no longer aims itself. A '
                      'wire crossing it at an angle needs a wider hole '
                      'than its own thickness — half again at fifty '
                      'degrees, twice at sixty — so I, K, J and L turn '
                      'the wrist, and a bend has to be turned into '
                      'before you are in it.'))
    else:
        said.append(_('The loop still aims itself along the wire here, so '
                      'the four turning keys do nothing yet.'))
    said.append(_('No touches at all are allowed.') if not grade.touches
                else _('One touch is allowed before the run is lost.')
                if grade.touches == 1
                else _('%d touches are allowed before the run is lost.')
                % grade.touches)
    if grade.view:
        said.append(_('The camera stands %d° round towards the wire\'s own '
                      'run, which is what makes a bend towards you and a '
                      'bend away from you hard to tell apart. The shadow '
                      'on the board is the cue that is left.')
                    % int(grade.view))
    if chosen['BUZZ_ADAPTIVE']:
        said.append(_('Get home with time to spare and the next wire is a '
                      'level harder; lose one and it is a level easier.'))
    return '  '.join(said)


BUZZ_WIRE = TaskSpec(
    title=_('Buzz Wire options'),
    options=(
        Option('BUZZ_LEVEL', _('Level'), 2, values=tuple(range(1, 13))),
        Option('BUZZ_TRIALS', _('Wires per run'), 3,
               values=(1, 2, 3, 5, 8, 10)),
        Option('BUZZ_ADAPTIVE',
               _('Climb a level when you get home with time to spare'), True),
        Option('BUZZ_METER', _('Show how much of the gap is gone'), True),
        Option('BUZZ_BEADS', _('String milestones along the wire'), True),
        Option('BUZZ_SIGHT', _('Show the view down the wire'), True),
    ),
    note=buzz_wire_note)


def sokoban_note(chosen: Dict[str, Any]) -> str:
    """What the chosen rung is made of, and what the par will mean."""
    from ..sokoban import GRADES
    rung = int(chosen['SOKOBAN_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s": a %dx%d room, %d %s, certified to '
              'need at least %d pushes.')
            % (rung, _(grade.name), grade.width, grade.height,
               grade.boxes, _('box') if grade.boxes == 1 else _('boxes'),
               grade.floor)]
    if grade.trap_share:
        said.append(_('At least %d%% of the floor is a trap: one '
                      'wrong push there and the box is lost for '
                      'good.') % int(grade.trap_share * 100))
    if grade.deceit:
        said.append(_('And at least %d%% of the pushes open to you on '
                      'move one throw the level away outright.')
                    % int(grade.deceit * 100))
    if rung >= 11:
        said.append(_('Up here the exact minimum outgrows the '
                      'solver; the par is a proven lower bound, '
                      'never pretending to be a minimum.'))
    if chosen['SOKOBAN_ADAPTIVE']:
        said.append(_('Solve near the minimum and the next puzzle '
                      'climbs a level; flounder and it steps down.'))
    return '  '.join(said)


SOKOBAN = TaskSpec(
    title=_('Sokoban options'),
    options=(
        Option('SOKOBAN_LEVEL', _('Start at level'), 2,
               values=tuple(range(1, 17))),
        Option('SOKOBAN_TRIALS', _('Puzzles per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('SOKOBAN_ADAPTIVE',
               _('Climb a level when you solve near the minimum'), True),
        Option('SOKOBAN_SHOW_TRAPS',
               _('Mark the squares a box dies on'), False),
    ),
    note=sokoban_note)


def maze_note(chosen: Dict[str, Any]) -> str:
    """What the chosen rung is made of, and what the par will mean.

    The two axes are both named here because the second one is not
    visible on screen: a maze that punishes fetching the keys in the
    wrong order looks exactly like one that does not, and the only
    way to know the rung guarantees it is to be told.
    """
    from ..maze import GRADES
    rung = int(chosen['MAZE_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s": a %d by %d maze%s, and never fewer than '
              '%d steps to get out.')
            % (rung, _(grade.name), 2 * grade.rooms + 1, 2 * grade.rooms + 1,
               (_(' behind %d locked doors') % grade.doors) if grade.doors
               else '', grade.floor)]
    if grade.braid:
        said.append(_('About %d%% of the dead ends are opened back into '
                      'the maze, so there is more than one way round.')
                    % int(grade.braid * 100))
    if grade.planning:
        said.append(_('And fetching the keys nearest-first throws away '
                      'at least %d%% of the walk, so the order is the '
                      'puzzle.') % int(grade.planning * 100))
    if not chosen['MAZE_SHOW_TRAIL']:
        said.append(_('Without the trail you have to carry the map '
                      'yourself.'))
    if chosen['MAZE_ADAPTIVE']:
        said.append(_('Get out within a quarter of the minimum and the '
                      'next maze is a level harder.'))
    return '  '.join(said)


MAZE = TaskSpec(
    title=_('Maze options'),
    options=(
        Option('MAZE_LEVEL', _('Level'), 2,
               values=tuple(range(1, 16))),
        Option('MAZE_TRIALS', _('Mazes per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('MAZE_SHOW_TRAIL', _('Mark where you have been'), True),
        Option('MAZE_ADAPTIVE',
               _('Climb a level when you get out near the minimum'), True),
    ),
    note=maze_note)


def in_the_dark_note(chosen: Dict[str, Any]) -> str:
    """What the rung buries, and what remembering less than it is worth.

    The floor is spelled out in rooms because it is the one number on
    the ladder that is a guarantee rather than an average: below it a
    player holds no information at all, so it is worth saying what
    "level 9" actually costs before it is chosen.
    """
    from ..inthedark import GRADES
    rung = int(chosen['DARK_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s": %d lamps in %d colours, %d rooms, and %d '
              'of the lamps asked about at the end.')
            % (rung, _(grade.name), grade.lamps, grade.colours, grade.depth,
               grade.asks)]
    said.append(_('The answer is never nearer than %d rooms from the end, '
                  'so remembering the last %d of them is worth exactly '
                  'nothing — one guess in %d.')
                % (grade.floor, grade.floor - 1, grade.colours))
    seconds = float(chosen['DARK_SECONDS'])
    said.append(_('At %.1fs a room that is about %d seconds of walking '
                  'before the first question.')
                % (seconds, int(round(seconds * grade.depth))))
    if chosen['DARK_ADAPTIVE']:
        said.append(_('Answer every question and the next round is a '
                      'level harder.'))
    return '  '.join(said)


IN_THE_DARK = TaskSpec(
    title=_('In the Dark options'),
    options=(
        Option('DARK_LEVEL', _('Level'), 2,
               values=tuple(range(1, 13))),
        Option('DARK_TRIALS', _('Rounds per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('DARK_SECONDS', _('Seconds a room is shown'), 1.2,
               values=(0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0)),
        Option('DARK_ADAPTIVE',
               _('Climb a level after a clean round'), True),
    ),
    note=in_the_dark_note)


def removals_note(chosen: Dict[str, Any]) -> str:
    """What the rung buries, how deep it composes, and what chance is.

    Two numbers are spelled out because they are the two the ladder
    actually promises, and they are easy to confuse: how far back the
    answer sits, and how many facts it is made of. A chain twenty
    moves back but one hop long is a long wait; a chain five hops long
    is five things remembered from five different moments.
    """
    from ..removals import GRADES
    rung = int(chosen['REMOVALS_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s": %d vans, %d boxes and %d things, moved %d '
              'times, with %d of the things asked about at the end.')
            % (rung, _(grade.name), grade.vans, grade.boxes, grade.items,
               grade.depth, grade.asks)]
    said.append(_('Every answer is %d hops deep — a thing in a box, that '
                  'box in another, and so on to a van — and none is '
                  'pinned nearer than %d moves from the end, so '
                  'remembering the last %d of them is worth exactly '
                  'nothing: one guess in %d.')
                % (grade.nest, grade.floor, grade.floor - 1, grade.vans))
    seconds = float(chosen['REMOVALS_SECONDS'])
    said.append(_('At %.1fs a move that is about %d seconds of loading '
                  'before the first question.')
                % (seconds, int(round(seconds * grade.depth))))
    if chosen['REMOVALS_ADAPTIVE']:
        said.append(_('Answer every question and the next round is a '
                      'level harder.'))
    return '  '.join(said)


REMOVALS = TaskSpec(
    title=_('Removals options'),
    options=(
        Option('REMOVALS_LEVEL', _('Level'), 3,
               values=tuple(range(1, 13))),
        Option('REMOVALS_TRIALS', _('Rounds per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('REMOVALS_SECONDS', _('Seconds a move is shown'), 1.2,
               values=(0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0)),
        Option('REMOVALS_ADAPTIVE',
               _('Climb a level after a clean round'), True),
    ),
    note=removals_note)


def fog_of_war_note(chosen: Dict[str, Any]) -> str:
    """What the eye reaches, and what the map does or does not keep.

    The quiet screen is worth mentioning here, because it reads as a
    missing feature rather than as the design it is: there is no step
    counter and no coverage bar on purpose, and this is the only place
    a player is told why.
    """
    from ..fogworld import ROOMS_ACROSS, ROOMS_DOWN
    radius = int(chosen['FOG_RADIUS'])
    said = [_('A %d by %d world of corridors, seen %d cells at a time.')
            % (2 * ROOMS_ACROSS + 1, 2 * ROOMS_DOWN + 1, radius)]
    if chosen['FOG_PERSIST']:
        said.append(_('Ground stays lit once you have seen it, so a map '
                      'builds up as you go.'))
    else:
        said.append(_('Only the circle around you is ever lit, so the map '
                      'is yours to carry.'))
    said.append(_('%d moves a world, and walking into a wall spends one '
                  'and changes nothing — there is no counter and no '
                  'progress bar on screen, deliberately, so that going '
                  'somewhere new is the only thing that can make the '
                  'picture change.') % int(chosen['FOG_MOVES']))
    return '  '.join(said)


FOG_OF_WAR = TaskSpec(
    title=_('Fog of War options'),
    options=(
        Option('FOG_RADIUS', _('How far you can see'), 2,
               values=(1, 2, 3, 4, 5)),
        Option('FOG_MOVES', _('Moves per world'), 400,
               values=(100, 200, 300, 400, 600, 800, 1200)),
        Option('FOG_WORLDS', _('Worlds per run'), 3,
               values=(1, 2, 3, 5, 8, 10)),
        Option('FOG_PERSIST', _('Keep the map you have uncovered'), True),
    ),
    note=fog_of_war_note)


def you_are_here_note(chosen: Dict[str, Any]) -> str:
    """What the map will and will not do, and what the top rungs cost.

    Two things get spelled out because both read as bugs otherwise:
    that the map genuinely never moves — people wait for it to start
    following them — and that a big maze takes about a second to
    appear. Measured at the top rung, the larger share of that is the
    2D Maze's own generator hunting for a maze that meets the rung's
    floors, which is a wait this task inherits rather than adds.
    """
    from ..maze import GRADES
    rung = int(chosen['HERE_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    across = 2 * grade.rooms + 1
    said = [_('Level %d, "%s": a %d by %d maze with %d doors — the very '
              'same maze the 2D Maze deals at this level, walked from '
              'inside it.') % (rung, _(grade.name), across, across,
                               grade.doors)]
    said.append(_('The map beside the view shows all of it, including '
                  'where you started and where the way out is. It never '
                  'moves and it never says where you are — that part is '
                  'yours to keep track of, and it is the whole task.'))
    said.append(_('Turning costs a step, so looking around is a decision '
                  'rather than something free; the par runs about a '
                  'quarter above the flat one next door for that reason. '
                  'Walking into a wall costs nothing.'))
    if not chosen['HERE_MARKS']:
        said.append(_('With the marks off there is nothing hanging in the '
                      'corridors at all, so a count of corners is the only '
                      'thing you will have.'))
    if grade.rooms >= 14:
        said.append(_('A maze this size takes about a second to deal, '
                      'most of it spent generating a maze that meets the '
                      "rung's floors rather than solving it."))
    if chosen['HERE_ADAPTIVE']:
        said.append(_('Get out near the minimum and the next maze is a '
                      'level harder.'))
    return '  '.join(said)


YOU_ARE_HERE = TaskSpec(
    title=_('3D Maze options'),
    options=(
        Option('HERE_LEVEL', _('Level'), 2, values=tuple(range(1, 16))),
        Option('HERE_TRIALS', _('Mazes per run'), 3,
               values=(1, 2, 3, 5, 8, 10)),
        Option('HERE_ADAPTIVE',
               _('Climb a level when you get out near the minimum'), True),
        Option('HERE_MARKS',
               _('Show keys and the way out in the corridors'), True),
    ),
    note=you_are_here_note)


def sokoban_3d_note(chosen: Dict[str, Any]) -> str:
    """What the plan will and will not do, and what the par will mean.

    Three things get spelled out because all three read as bugs
    otherwise: that the plan genuinely never moves, that it goes on
    showing the boxes where they *started* however far you have shoved
    them, and that above the rung where the step search runs out the
    par stops being a minimum and becomes a proven lower bound.
    """
    from ..sokoban import GRADES
    rung = int(chosen['SOKO3D_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s": a %dx%d warehouse with %d %s — the very '
              'same room the 2D Sokoban deals at this level, pushed '
              'from inside it.')
            % (rung, _(grade.name), grade.width, grade.height, grade.boxes,
               _('box') if grade.boxes == 1 else _('boxes'))]
    said.append(_('The plan beside the view shows all of it, including '
                  'where you came in and where every box was standing '
                  'then. It never moves, it never says where you are, '
                  'and it never says where the boxes are now — your '
                  'first push makes it out of date and nothing puts it '
                  'right again.'))
    said.append(_('Turning costs a step, so looking around is a decision '
                  'rather than something free, and the par is in steps '
                  'rather than pushes for that reason — about three and '
                  'a half times the push count next door. Walking into '
                  'rock, or shoving a box that will not go, costs '
                  'nothing.'))
    if rung >= 9:
        said.append(_('Up here the exact step minimum outgrows the '
                      'search; the par is a proven lower bound, never '
                      'pretending to be a minimum. Dealing a level '
                      'takes a second or two.'))
    if grade.trap_share:
        said.append(_('At least %d%% of the floor is a trap: one wrong '
                      'push there and the box is lost for good, and '
                      'from inside a corridor you cannot see the pocket '
                      'coming.') % int(grade.trap_share * 100))
    if not chosen['SOKO3D_MARKS']:
        said.append(_('With the rings off there is nothing hanging in '
                      'the corridors at all, so a count of corners is '
                      'the only thing you will have.'))
    if chosen['SOKO3D_ADAPTIVE']:
        said.append(_('Finish near the minimum and the next warehouse '
                      'is a level harder.'))
    return '  '.join(said)


SOKOBAN_3D = TaskSpec(
    title=_('3D Sokoban options'),
    options=(
        Option('SOKO3D_LEVEL', _('Level'), 2, values=tuple(range(1, 13))),
        Option('SOKO3D_TRIALS', _('Warehouses per run'), 3,
               values=(1, 2, 3, 5, 8, 10)),
        Option('SOKO3D_ADAPTIVE',
               _('Climb a level when you finish near the minimum'), True),
        Option('SOKO3D_MARKS',
               _('Show the goals as rings in the corridors'), True),
        Option('SOKO3D_TRAPS',
               _('Mark the squares a box dies on, on the plan'), False),
    ),
    note=sokoban_3d_note)


def tetris_note(chosen: Dict[str, Any]) -> str:
    """What the chosen well and rung amount to, and what is promised.

    The promise is the line worth printing here rather than only in
    the game: whatever these dials say, every piece on offer will have
    somewhere to go that buries nothing. The rung changes how hard
    that somewhere is to see, and nothing on this screen changes how
    fast it arrives.
    """
    from .. import tetris
    columns = int(chosen['TETRIS_COLUMNS'])
    rows = int(chosen['TETRIS_ROWS'])
    grade = tetris.grade_at(int(chosen['TETRIS_RUNG']))
    least, most = grade.cells
    said = [_('A %dx%d well is %d cells — a tetris well is 200.')
            % (columns, rows, columns * rows),
            _('Rung %d cuts %s: %d to %d cells across %d to %d columns.')
            % (int(chosen['TETRIS_RUNG']), grade.name, least, most,
               grade.span[0], grade.span[1])]
    detent = int(chosen['TETRIS_DETENT'])
    said.append(_('Every angle in the circle is held exactly as wound.')
                if not detent else
                _('Within %d° of a quarter turn the piece is held '
                  'square, which is the only way a drop can be sure of '
                  'burying nothing; S squares up on purpose.') % detent)
    if chosen['TETRIS_ADAPTIVE']:
        said.append(_('Six placements in a row with no gap climbs a rung; '
                      'gaps fall off one.'))
    said.append(_('Gravity stays at %g cells a second on every rung — '
                  'the ladder is shape, not speed.')
                % float(chosen['TETRIS_FALL']))
    return '  '.join(said)


TETRIS = TaskSpec(
    title=_('Freeform Tetris options'),
    options=(
        Option('TETRIS_RUNG', _('Starting rung'), 1,
               values=tuple(range(1, 9))),
        Option('TETRIS_COLUMNS', _('Columns in the well'), 72,
               values=(32, 48, 64, 72, 80, 96)),
        Option('TETRIS_ROWS', _('Rows in the well'), 32,
               values=(20, 24, 32, 40)),
        Option('TETRIS_PIECES', _('Pieces per run'), 25,
               values=(10, 15, 25, 40, 60, 100)),
        Option('TETRIS_QUEUE', _('Pieces to choose between'), 5,
               values=(2, 3, 4, 5, 6)),
        Option('TETRIS_FALL', _('Gravity'), 2.5,
               values=(1.0, 1.5, 2.5, 4.0, 6.0), suffix=_(' cells/s')),
        Option('TETRIS_SPIN', _('Spin rate while a key is held'), 150,
               values=(60, 90, 150, 220, 320), suffix=_('°/s')),
        Option('TETRIS_DETENT', _('Pull onto the grid within'), 7,
               values=(0, 3, 7, 12), suffix=_('° of a quarter turn')),
        Option('TETRIS_ADAPTIVE',
               _('Climb a rung after a run of placements with no gap'),
               True),
        Option('TETRIS_GHOST', _('Show where the piece would land'), True),
    ),
    note=tetris_note)


def crossed_wires_note(chosen: Dict[str, Any]) -> str:
    """What is scrambled, how little is spare, and what moves under you.

    The spare presses are spelled out as a number rather than left
    implicit in the level, because they are the whole difficulty of
    the junior rungs: with twelve to waste a player can try every key
    twice before deciding, and with two it cannot try them all once.
    """
    from ..crossedwires import CROSSED, MIRRORED, STEADY, GRADES
    rung = int(chosen['WIRES_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    scrambled = {STEADY: _('not scrambled at all — the keys go where they '
                           'say, so this rung is the one to check the rest '
                           'against'),
                 MIRRORED: _('reflected, which is the one people find '
                             'hardest: you cannot lean your way out of a '
                             'mirror the way you can out of a turn'),
                 CROSSED: _('scrambled outright, any way at all')}.get(
                     grade.family, _('turned bodily round the ring'))
    said = [_('Level %d, "%s": %d keys on a %d by %d grid that wraps at '
              'every edge, %d targets, and the wiring %s.')
            % (rung, _(grade.name), grade.keys, grade.across, grade.down,
               grade.targets, scrambled)]
    said.append(_('You get the shortest trip plus %d presses and no more, '
                  'so every key you try out costs one of those %d.')
                % (grade.spare, grade.spare))
    if grade.drift:
        said.append(_('The whole wiring turns, silently, every %d presses '
                      '— so whatever you worked out goes stale and there '
                      'is no notice that it has.') % grade.drift)
    if grade.dies:
        said.append(_('And one key stops working after press %d, also '
                      'silently.') % grade.dies)
    if chosen['WIRES_ADAPTIVE']:
        said.append(_('Reach every target and the next round is a level '
                      'harder.'))
    return '  '.join(said)


CROSSED_WIRES = TaskSpec(
    title=_('Crossed Wires options'),
    options=(
        Option('WIRES_LEVEL', _('Level'), 3, values=tuple(range(1, 13))),
        Option('WIRES_ROUNDS', _('Rounds per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('WIRES_ADAPTIVE',
               _('Climb a level after a clean round'), True),
        Option('WIRES_GRID', _('Draw the cell lines'), True),
    ),
    note=crossed_wires_note)


def sudoku_note(chosen: Dict[str, Any]) -> str:
    """What the rung forces, and the two things that surprise people.

    The deal cost is spelled out because the top rungs really do
    pause: a difficulty cannot be dug towards, only dealt and rated,
    so a rare band is found by dealing until one turns up. And the
    clash marker is named as the difficulty setting it is, rather
    than as a display option, because turning it off is a bigger
    jump than a rung.
    """
    from ..sudoku import GRADES, TECHNIQUES
    rung = int(chosen['SUDOKU_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    size = grade.box * grade.box
    said = [_('Level %d, "%s": a %d by %d grid, and %s.')
            % (rung, _(grade.name), size, size,
               (_('nothing deeper than %s') % _(TECHNIQUES[grade.ceiling]))
               if grade.ceiling < len(TECHNIQUES) - 1
               else _('more than plain deduction will finish'))]
    if grade.guesses:
        said.append(_('Past the technique stack it still takes at least '
                      '%d guesses to close.') % grade.guesses)
    if grade.box == 4:
        said.append(_('Sixteens run on 1-9 and then A-G.'))
    if not chosen['SUDOKU_SHOW_CLASHES']:
        said.append(_('With clashes unmarked nothing is checked until the '
                      'grid is full, which is a long way harder than any '
                      'one rung of the ladder.'))
    if grade.tries > 60 or grade.box == 4:
        said.append(_('This rung takes a second or two to deal: a '
                      'difficulty cannot be aimed at, only dealt and '
                      'rated.'))
    return '  '.join(said)


SUDOKU = TaskSpec(
    title=_('Sudoku options'),
    options=(
        Option('SUDOKU_LEVEL', _('Level'), 3,
               values=tuple(range(1, 13))),
        Option('SUDOKU_TRIALS', _('Puzzles per run'), 3,
               values=(1, 2, 3, 5, 8, 10)),
        Option('SUDOKU_SHOW_CLASHES', _('Mark a digit that clashes'), True),
        Option('SUDOKU_ADAPTIVE',
               _('Climb a level after a clean solve'), True),
    ),
    note=sudoku_note)


def ninarow_note(chosen: Dict[str, Any]) -> str:
    """Explain the board the selected rung will actually deal."""
    from .. import ninarow
    rung = int(chosen['NINAROW_LEVEL'])
    grade = ninarow.grade_at(rung)
    grid = int(chosen['NINAROW_GRID']) or grade.size
    pellets = int(chosen['NINAROW_PELLETS']) or grade.pellets
    length = int(chosen['NINAROW_LENGTH']) or grade.length
    said = [_('Level %d, "%s": a %d by %d board with about %d pellets; '
              'find %d in a row.')
            % (rung, _(grade.name), grid, grid, pellets, length),
            _('Find the one empty cell that completes the line. '
              'The board is a scenario, not a game against the computer.')]
    if not chosen['NINAROW_GRID'] and not chosen['NINAROW_PELLETS'] \
            and not chosen['NINAROW_LENGTH']:
        said.append(_('The board, pellet count, and line length grow with '
                      'the level.'))
    else:
        said.append(_('A non-zero grid, pellet, or line-length setting '
                      'overrides that part of the level.'))
    if chosen['NINAROW_ADAPTIVE']:
        said.append(_('A right answer climbs one level; a miss falls one.'))
    return '  '.join(said)


NINAROW = TaskSpec(
    title=_('N-in-a-row options'),
    options=(
        Option('NINAROW_LEVEL', _('Starting level'), 1,
               values=tuple(range(1, 10))),
        Option('NINAROW_TRIALS', _('Positions per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15)),
        Option('NINAROW_GRID', _('Grid size (0 follows level)'), 0,
               values=(0, 5, 6, 8, 12, 16, 24, 32, 64, 128)),
        Option('NINAROW_PELLETS', _('Pellets (0 follows level)'), 0,
               values=(0, 7, 12, 22, 45, 80, 150, 300, 1200, 6000)),
        Option('NINAROW_LENGTH', _('Line length (0 follows level)'), 0,
               values=(0, 3, 4, 5, 8, 15, 40, 100)),
        Option('NINAROW_SHOW_ANSWER', _('Mark the winning cell afterwards'),
               True),
        Option('NINAROW_ADAPTIVE', _('Climb a level after a right answer'),
               True),
    ),
    note=ninarow_note)


def crossword_note(chosen: Dict[str, Any]) -> str:
    """What the grid will look like, and the two things people ask.

    The word pool is named first when it is missing, because that is
    the only setting on this screen that can stop the task from
    dealing anything at all, and finding that out from a blank screen
    is worse than reading it here.
    """
    from ..crossword import GRADES
    from ..wordlist import CLUES, have, index_ready
    rung = int(chosen['CROSSWORD_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = []
    if not (index_ready() and have(CLUES)):
        said.append(_('No clues here yet: run '
                      '"python -m neural_workshop.wordlist" once, which '
                      'fetches about 100 MB into your data directory.'))
    said.append(_('Level %d, "%s": a %d by %d grid, %s, drawn from %s.')
                % (rung, _(grade.name), grade.size, grade.size,
                   (_('every row and column a word')
                    if grade.longest_entry >= grade.size
                    else _('entries up to %d letters') % grade.longest_entry),
                   (_('the whole word list') if grade.top_rank > 1 << 20
                    else _('the %d commonest words') % grade.top_rank)))
    if grade.given:
        said.append(_('About %d letters in a hundred are written in for '
                      'you.') % int(grade.given * 100))
    if grade.withheld:
        said.append(_('One entry in %d gets no clue at all and has to '
                      'come from its crossings.')
                    % max(2, int(round(1 / grade.withheld))))
    if not chosen['CROSSWORD_SHOW_MISTAKES']:
        said.append(_('With mistakes unmarked nothing is checked until '
                      'the grid is full, which is a long way harder than '
                      'any one level.'))
    said.append(_('The clues are made from definitions a language model '
                  'wrote, so one can be wrong.'))
    return '  '.join(said)


CROSSWORD = TaskSpec(
    title=_('Crossword options'),
    options=(
        Option('CROSSWORD_LEVEL', _('Level'), 2, values=tuple(range(1, 11))),
        Option('CROSSWORD_TRIALS', _('Grids per run'), 3,
               values=(1, 2, 3, 5, 8, 10)),
        Option('CROSSWORD_SHOW_MISTAKES', _('Mark a wrong letter'), True),
        Option('CROSSWORD_ADAPTIVE',
               _('Climb a level after a clean solve'), True),
    ),
    note=crossword_note)


def scrabble_note(chosen: Dict[str, Any]) -> str:
    """What the board will be, and what green will take.

    The passing share is spelled out as a number because it is the
    whole of what a level means here: everything else on the board is
    the same game at every rung.
    """
    from ..scrabble import GRADES
    rung = int(chosen['SCRABBLE_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s": a %d by %d board with %s already '
              'on it, a rack of %d, and the best play drawn from %s.')
            % (rung, _(grade.name), grade.size, grade.size,
               _('one word') if grade.seeded == 1
               else _('%d words') % grade.seeded,
               grade.rack,
               (_('the whole word list') if grade.top_rank > 1 << 20
                else _('the %d commonest words') % grade.top_rank))]
    said.append(_('Green takes %d%% of the best play there was.')
                % int(round(grade.share * 100)))
    if grade.share >= 1.0:
        said.append(_('Which at this level means the best play and '
                      'nothing else.'))
    said.append(_('Standard letter values and distribution; no blanks '
                  'are dealt.'))
    return '  '.join(said)


SCRABBLE = TaskSpec(
    title=_('Scrabble options'),
    options=(
        Option('SCRABBLE_LEVEL', _('Level'), 3, values=tuple(range(1, 11))),
        Option('SCRABBLE_TRIALS', _('Boards per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15)),
        Option('SCRABBLE_SHOW_PREMIUMS', _('Paint the premium squares'),
               True),
        Option('SCRABBLE_ADAPTIVE',
               _('Climb a level after a green play'), True),
    ),
    note=scrabble_note)


def scramble_note(chosen: Dict[str, Any]) -> str:
    """What will be done to the sentence, and how much of it survives.

    The text being Wikipedia's, the attribution belongs on the screen
    a player actually opens rather than only in a docstring, so it is
    the last line here whether or not anything has been fetched.
    """
    from ..scramble import GRADES
    from ..sentences import LICENCE, REPO, have, missing_message
    rung = int(chosen['SCRAMBLE_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = []
    if not have():
        said.append(missing_message())
    done = []
    if grade.swap:
        done.append(_('two letters of each word swapped'))
    elif grade.interior:
        done.append(_('the middle of each word shuffled'))
    elif grade.whole:
        done.append(_('every letter of each word shuffled'))
    if grade.drop:
        done.append(_('a letter thrown away') if grade.drop == 1
                    else _('%d letters thrown away') % grade.drop)
    if grade.insert:
        done.append(_('a letter thrown in'))
    if grade.substitute:
        done.append(_('a letter replaced by its neighbour on the keyboard'))
    if grade.spaces == 1:
        done.append(_('the gaps moved to the wrong places'))
    elif grade.spaces >= 2:
        done.append(_('the gaps taken out'))
    if grade.order >= 2:
        done.append(_('the words shuffled in threes') if grade.order >= 3
                    else _('the words shuffled in pairs'))
    said.append(_('Level %d, "%s": %d to %d words drawn from %s, with %s.')
                % (rung, _(grade.name), grade.span[0], grade.span[1],
                   (_('the whole word list') if grade.top_rank > 1 << 20
                    else _('the %d commonest words') % grade.top_rank),
                   ', '.join(str(one) for one in done) or _('nothing done')))
    if grade.spaces == 1:
        said.append(_('The gaps on screen are not where the words are, so '
                      'the word count is worth turning on.'))
    elif grade.spaces >= 2:
        said.append(_('There are no gaps at all, so the word count is '
                      'worth turning on.'))
    said.append(_('Type the sentence back. Nothing partial counts: a '
                  'reading that is one letter out is a different sentence.'))
    said.append(_('Text from %s, %s.') % (REPO, LICENCE))
    return '  '.join(said)


SCRAMBLE = TaskSpec(
    title=_('Scramble options'),
    options=(
        Option('SCRAMBLE_LEVEL', _('Level'), 3, values=tuple(range(1, 13))),
        Option('SCRAMBLE_TRIALS', _('Lines per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15)),
        Option('SCRAMBLE_SHOW_COUNT', _('Say how many words'), True),
        Option('SCRAMBLE_ADAPTIVE',
               _('Climb a level after a right answer'), True),
    ),
    note=scramble_note)


def overrun_note(chosen: Dict[str, Any]) -> str:
    """What the level asks of the fingers, in the units typing is sold in.

    Words a minute rather than an adjective, because it is the one
    number a player already knows their own value of, and because it is
    measured over the sentences the rung actually deals rather than
    read off the drift — the gaps are cells the line has to cross and
    are not keys anybody presses.

    The text being Wikipedia's, the attribution belongs on a screen a
    player opens rather than only in a docstring.
    """
    from ..overrun import (GRADES, LONGEST, MOST_LIVES, SHORTEST, TOP_RANK,
                           pace)
    from ..sentences import LICENCE, REPO, have, missing_message
    rung = int(chosen['OVERRUN_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = []
    if not have():
        said.append(missing_message())
    said.append(_('Level %d, "%s": the line crosses %.1f characters a '
                  'second, which asks for about %d words a minute.')
                % (rung, _(grade.name), grade.speed, int(round(pace(rung)))))
    said.append(_('Every level deals the same sentences — %d to %d '
                  'characters, out of the %s commonest words — so what '
                  'changes between the first and the twelfth is the clock '
                  'and nothing else.')
                % (SHORTEST, LONGEST, '{:,}'.format(TOP_RANK)))
    said.append(_('A wave starts with as much clear road ahead of it as it '
                  'has characters, so a long sentence and a short one ask '
                  'for the same rate.'))
    said.append(_('Clear a whole sentence and a life comes back, up to %d; '
                  'let one run out and a life goes. The run ends when the '
                  'lives do.') % MOST_LIVES)
    said.append(_('A wrong letter stays until it is rubbed out.'))
    said.append(_('Text from %s, %s.') % (REPO, LICENCE))
    return '  '.join(said)


OVERRUN = TaskSpec(
    title=_('Overrun options'),
    options=(
        Option('OVERRUN_LEVEL', _('Level'), 4, values=tuple(range(1, 13))),
        Option('OVERRUN_WAVES', _('Sentences per run'), 8,
               values=(3, 5, 8, 12, 20, 30)),
        Option('OVERRUN_ADAPTIVE',
               _('Climb a level after a cleared sentence'), True),
    ),
    note=overrun_note)


def algebra_note(chosen: Dict[str, Any]) -> str:
    """What the level asks, and how big the search behind it is.

    The search size is the honest description of a level here and it
    is a measured number rather than a word, so it is quoted rather
    than paraphrased into "hard".
    """
    from ..algebra import EXPRESSION, GRADES, deal_one
    import random
    rung = int(chosen['ALGEBRA_LEVEL'])
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s".') % (rung, _(grade.name))]
    said.append(_('The answer is a polynomial, gathered up: no brackets '
                  'left in it.') if grade.kind == EXPRESSION
                else _('The answer is a number, exact: a fraction stays a '
                       'fraction and a decimal is not an answer.'))
    shown = deal_one(grade, random.Random(rung))
    if shown is not None:
        said.append(_('Like this one: %s') % shown.asked)
        said.append(_('Before you do any of the work, the answer is one '
                      'of about 10^%d.') % round(shown.candidates))
    said.append(_('Nothing partial counts.'))
    return '  '.join(said)


ALGEBRA = TaskSpec(
    title=_('Algebra options'),
    options=(
        Option('ALGEBRA_LEVEL', _('Level'), 3, values=tuple(range(1, 13))),
        Option('ALGEBRA_TRIALS', _('Questions per run'), 6,
               values=(1, 2, 3, 5, 6, 8, 10, 15)),
        Option('ALGEBRA_SHOW_WORKING', _('Show the working afterwards'),
               True),
        Option('ALGEBRA_ADAPTIVE',
               _('Climb a level after a right answer'), True),
    ),
    note=algebra_note)


def numberology_note(chosen: Dict[str, Any]) -> str:
    """Describe the procedural length and rule family at a level."""
    from ..numberology import generate, sequence_length
    level = int(chosen['NUMBEROLOGY_LEVEL'])
    shown = generate(level, seed=level)
    return _('Level %d: %d numbers are shown. %s. A perfect session '
             'advances to level %d.') % (
                 level, sequence_length(level), _(shown.rule), level + 1)


NUMBEROLOGY = TaskSpec(
    title=_('Numberology options'),
    options=(
        # This row uses an unbounded integer cycler, so 10,000 and beyond are
        # reachable from the menu instead of being hidden behind a cap.
        Option('NUMBEROLOGY_LEVEL', _('Starting level'), 1, values=(1,)),
        Option('NUMBEROLOGY_TRIALS', _('Questions per session'), 6,
               values=(1, 2, 3, 5, 6, 8, 10, 15)),
        Option('NUMBEROLOGY_ADVANCE', _('Advance after a perfect session'),
               True),
    ),
    note=numberology_note)


def syllogism_note(chosen: Dict[str, Any]) -> str:
    """What the level asks, what it takes for granted, and an example.

    The convention is quoted rather than paraphrased, because it is a
    choice: with no ties in an order, "not more than" means "less
    than" and nothing else, and a player who guessed otherwise would
    be wrong about the task rather than about the premises.
    """
    from ..syllogism import GRADES, NOTHING, UNTOLD, deal_one, real_names
    import random
    rung = int(chosen['SYLLOGISM_LEVEL'])
    made_up = not chosen['SYLLOGISM_REAL_WORDS']
    grade = GRADES[max(0, min(len(GRADES) - 1, rung - 1))]
    said = [_('Level %d, "%s".') % (rung, _(grade.name))]
    shown = deal_one(grade, random.Random(rung), made_up)
    if shown is not None:
        said.append(_('%d lines, %d answers.') % (len(shown.lines),
                                                  len(shown.options)))
        said.append(_('Like this one: %s  %s')
                    % ('  /  '.join(shown.lines[:2])
                       + ('  ...' if len(shown.lines) > 2 else ''),
                       shown.asked))
        if not set(shown.options) & {UNTOLD, NOTHING}:
            said.append(_('This level always settles the question, so it '
                          'does not offer "cannot be told".'))
    said.append(_('One answer, and nothing partial counts.'))
    if made_up:
        said.append(_('Made-up names, which is the older way and not a '
                      'worse one: a real word carries a belief, and the '
                      'measured cost of that is on the two categorical '
                      'levels.'))
    elif not real_names():
        said.append(_('No word list has been fetched, so the things are '
                      'named with made-up words whatever this says. Run '
                      '"python -m neural_workshop.wordlist" once to name '
                      'them after ordinary ones.'))
    return '  '.join(said)


SYLLOGISM = TaskSpec(
    title=_('Syllogism options'),
    options=(
        Option('SYLLOGISM_LEVEL', _('Level'), 3, values=tuple(range(1, 13))),
        Option('SYLLOGISM_TRIALS', _('Questions per run'), 6,
               values=(1, 2, 3, 5, 6, 8, 10, 15)),
        Option('SYLLOGISM_SHOW_WORKING', _('Show the working afterwards'),
               True),
        Option('SYLLOGISM_ADAPTIVE',
               _('Climb a level after a right answer'), True),
        Option('SYLLOGISM_REAL_WORDS',
               _('Name things after real words'), True),
    ),
    note=syllogism_note)


def trivia_note(chosen: Dict[str, Any]) -> str:
    """What the rung offers, and which pool it will come out of.

    The pool is the line worth printing here rather than only in the
    game. A player dealing from the built-in questions will meet them
    all inside a few runs, and the difference between *this task is
    repetitive* and *this task has not been fetched* is one command.
    """
    from .. import trivia
    rung = int(chosen['TRIVIA_LEVEL'])
    grade = trivia.grade_at(rung)
    pool = trivia.bank()
    said = [_('Level %d, "%s": %d options.')
            % (rung, _(grade.name), grade.options)]
    said.append(_('The wrong answers are other questions\' right ones, '
                  'drawn from answers of the same shape — a year against '
                  'years, a name against names — so that what an option '
                  'looks like says nothing about whether it is right.')
                if grade.matched else
                _('The wrong answers are other questions\' right ones, '
                  'drawn from anywhere, so a year is often the only date '
                  'on the screen. From level %d they are matched by '
                  'shape.') % (1 + sum(1 for one in trivia.GRADES
                                       if not one.matched)))
    said.append(_('%d questions in the pool.') % len(pool))
    if not trivia.fetched():
        said.append(_('They are the ones written into the game, and there '
                      'are not many. Run "python -m neural_workshop.trivia" '
                      'once to fetch %d of %s\'s own (%s).')
                    % (trivia.DEFAULT_FETCH, trivia.REPO, trivia.LICENCE))
    elif pool.narrowest() < grade.options - 1 and grade.matched:
        said.append(_('One of the shapes holds only %d answers, so a '
                      'question with that shape of answer will be filled '
                      'out with others.') % pool.narrowest())
    return '  '.join(said)


TRIVIA = TaskSpec(
    title=_('Trivia options'),
    options=(
        Option('TRIVIA_LEVEL', _('Level'), 3, values=tuple(range(1, 8))),
        Option('TRIVIA_TRIALS', _('Questions per run'), 10,
               values=(1, 2, 3, 5, 10, 15, 25, 50)),
        Option('TRIVIA_SHOW_ANSWER', _('Mark the right answer afterwards'),
               True),
        Option('TRIVIA_ADAPTIVE',
               _('Climb a level after a right answer'), True),
    ),
    note=trivia_note)

def marble_maze_note(chosen: Dict[str, Any]) -> str:
    """What this rung's tray is, and the two things that surprise people.

    Both surprises are physics rather than rules, which is why they are
    said here rather than left to be discovered: that a marble can
    outrun a hole if it is going fast enough, and that on a
    several-marble tray the one pair of knobs moves all of them.
    """
    rung = int(chosen['MARBLE_MAZE_LEVEL'])
    grade = _MARBLE_GRADES[max(0, min(len(_MARBLE_GRADES) - 1, rung - 1))]
    corridor = 2.0 * 7.5 * grade.slack
    said = [_('Level %d, "%s": a %dx%d maze in corridors %dmm wide, with '
              '%d %s to miss and %d %s to bring home, in %ds.')
            % (rung, _(grade.name), grade.cols, grade.rows, round(corridor),
               grade.holes, _('hole') if grade.holes == 1 else _('holes'),
               grade.marbles,
               _('marble') if grade.marbles == 1 else _('marbles'),
               int(grade.seconds))]
    said.append(_('The marble is a 15mm steel one and it behaves like it: '
                  'it accelerates at five sevenths of gravity down the '
                  'slope, because the other two sevenths go into spin, '
                  'and it keeps rolling after you level the tray.'))
    said.append(_('A hole only takes a marble that is over it long enough '
                  'to fall in. Sent across fast enough, a marble clears '
                  'the far rim and lands with a clatter — which is the '
                  'only reason to ever go fast.'))
    if grade.marbles > 1:
        said.append(_('There is one tray and one pair of knobs, so all %d '
                      'marbles feel every tilt. They start nose to tail '
                      'along the same route, and they knock each other '
                      'about.') % grade.marbles)
    said.append(_('Every tray is generated and then certified: a sweep of '
                  'every place the marble may legally stand proves there '
                  'is a way through before it is dealt.'))
    return ' '.join(said)


MARBLE_MAZE = TaskSpec(
    title=_('Marble Maze options'),
    options=(
        Option('MARBLE_MAZE_LEVEL', _('Level'), 1,
               values=tuple(range(1, len(_MARBLE_GRADES) + 1))),
        Option('MARBLE_MAZE_TRIALS', _('Trays per run'), 5,
               values=(1, 2, 3, 5, 8, 10)),
        Option('MARBLE_MAZE_ADAPTIVE',
               _('Climb a level when you finish a tray in good time'), True),
        Option('MARBLE_MAZE_SHADOWS', _('Cast shadows'), True),
        Option('MARBLE_MAZE_SECONDS', _('Seconds per tray'), 0,
               values=(0, 15, 30, 45, 60, 90, 120)),
    ),
    note=marble_maze_note)


VERBAL_REASONING = TaskSpec(
    title=_('Verbal Reasoning options'),
    options=(
        Option('VERBAL_REASONING_TRIALS', _('Questions per run'), 6,
               values=(1, 2, 3, 5, 6, 8, 10, 15)),
        Option('VERBAL_REASONING_EXPLANATION',
               _('Show the source explanation after answering'), True),
    ))


def salesman_note(chosen: Dict[str, Any]) -> str:
    """What the score means at this size, and that it is exact.

    The exact solver doubles in cost with every city, so the top of
    the range buys a real pause when a round starts — worth a warning
    here, where the number is being chosen, rather than a mystery
    freeze later.
    """
    cities = int(chosen['TSP_CITIES'])
    said = [_('%d cities; the score is your route against the shortest '
              'one possible, computed exactly.') % cities]
    if cities >= 16:
        said.append(_('Fair warning: solving %d cities exactly takes '
                      'the computer a moment, so each round starts '
                      'with a short pause.') % cities)
    if chosen['TSP_ADAPTIVE']:
        said.append(_('Come within a few per cent of it and the next '
                      'map grows a city.'))
    return '  '.join(said)


SALESMAN = TaskSpec(
    title=_('Traveling Salesman options'),
    options=(
        Option('TSP_CITIES', _('Cities to start with'), 7,
               values=tuple(range(5, 19))),
        Option('TSP_ROUNDS', _('Routes per run'), 5,
               values=(3, 5, 8, 10, 15, 20)),
        Option('TSP_ADAPTIVE',
               _('Add a city when you come near the optimum'), True),
        Option('TSP_SHOW_BEST',
               _('Show the shortest route after each answer'), True),
    ),
    note=salesman_note)


def custody_note(chosen: Dict[str, Any]) -> str:
    """What the rung puts on the belt, and what guessing is worth.

    The floor is spelled out because the percentage means very little
    without it: a run at rung three is guessing one in two and a half
    and one at rung ten one in six, so the same score is a different
    achievement. It is boxes divided by coats, which is exactly the
    field a player who has lost the box is choosing from.
    """
    from ..custody import GRADES
    grade = GRADES[max(0, min(len(GRADES) - 1,
                              int(chosen['CUSTODY_LEVEL']) - 1))]
    said = [_('%d boxes in %d coat(s): a colour leaves %.1f of them to '
              'choose between, so guessing scores about %d%%.')
            % (grade.boxes, grade.looks, grade.rivals,
               int(round(100.0 / grade.rivals)))]
    if not grade.moving:
        said.append(_('The belt is still at this rung.'))
    if grade.need_charge:
        said.append(_('The bay wants %d charge and under %d heat. One pass '
                      'through the charger clears the mark and leaves the '
                      'box too hot, so the cooler comes after it.')
                    % (grade.need_charge, grade.max_heat))
    if grade.painters:
        said.append(_('A painter moves the coat on of every box that rides '
                      'past it.'))
    if grade.decay:
        said.append(_('Charge bleeds away on the belt, though not in the '
                      'claw.'))
    said.append(_('%d actions a round.') % grade.budget)
    return '  '.join(said)


CUSTODY = TaskSpec(
    title=_('Chain of Custody options'),
    options=(
        Option('CUSTODY_LEVEL', _('Level'), 3,
               values=tuple(range(1, 11))),
        Option('CUSTODY_TRIALS', _('Rounds per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('CUSTODY_BELT_SECONDS', _('Seconds a slot of belt takes'),
               0.40, values=(0.15, 0.25, 0.40, 0.60, 0.90, 1.5)),
        Option('CUSTODY_MARK_SECONDS', _('Seconds the box is ringed for'),
               1.6, values=(0.4, 0.8, 1.2, 1.6, 2.5, 4.0)),
        Option('CUSTODY_ADAPTIVE',
               _('Climb a rung after a clean delivery'), True),
    ),
    note=custody_note)


def donkey_note(chosen: Dict[str, Any]) -> str:
    """What the rung asks, and what the two shallow policies are worth.

    Both numbers are measured rather than derived. The floor is the
    usual coin. The other one is the one worth reading: the share of
    roads cleared by swerving the moment the donkey is on the row
    ahead, which is what the game looks like it is asking for and is
    perfect play while the crossing is one row wide.
    """
    from ..donkey import GRADES, rehearse
    level = max(1, min(len(GRADES), int(chosen['DONKEY_LEVEL'])))
    grade = GRADES[level - 1]
    said = [_('%d rows of road, and about %d in ten of them carry a '
              'donkey.') % (grade.rows, int(round(10 * grade.density)))]
    said.append(_('The swerve takes one row, so the press goes in on the '
                  'row before the donkey.') if grade.swerve == 1 else
                _('The swerve takes %d rows and cannot be called off. While '
                  'the car is across the middle a donkey in either lane '
                  'hits it, so the press has to go in %d rows early and '
                  'swerving on sight is already too late.')
                % (grade.swerve, grade.swerve))
    said.append(_('Swerving on sight clears about %d%% of these roads. A '
                  'coin clears none of them at all: a press starts a '
                  'crossing it cannot call off, so pressing at random '
                  'leaves you across the middle most of the way.')
                % int(round(100 * rehearse(level, policy='reactive'))))
    return '  '.join(said)


DONKEY = TaskSpec(
    title=_('Donkey options'),
    options=(
        Option('DONKEY_LEVEL', _('Level'), 3,
               values=tuple(range(1, 11))),
        Option('DONKEY_TRIALS', _('Roads per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('DONKEY_BEAT_SECONDS', _('Seconds a row takes'),
               0.18, values=(0.08, 0.12, 0.18, 0.25, 0.40, 0.60)),
        Option('DONKEY_SET_SECONDS', _('Seconds before the road moves'),
               0.8, values=(0.0, 0.4, 0.8, 1.5, 2.5)),
        Option('DONKEY_ADAPTIVE', _('Climb a rung after a clean road'),
               True),
    ),
    note=donkey_note)


def two_hands_note(chosen: Dict[str, Any]) -> str:
    """What the rung deals, and what the two ways of taking the sky are worth.

    The last pair is the one to read and it is the same driver twice:
    shooting only on the ticks the wheel had no use for, against
    shooting the moment anything is up there. Measured rather than
    derived, and cached, so opening this screen is cheap after the
    first time.
    """
    from ..twohands import GRADES, KINDS, rehearse, sky_toll
    level = max(1, min(len(GRADES), int(chosen['TWOHANDS_LEVEL'])))
    grade = GRADES[level - 1]
    said = [_('%d rows, about %d in ten carrying something, top gear %d. '
              'The swerve takes %d ticks and covers both lanes for all of '
              'them, so the faster you go the more road you are across the '
              'middle for.')
            % (grade.rows, int(round(10 * grade.density)), grade.top,
               grade.swerve)]
    if any(not KINDS[kind].tall for kind in grade.kinds):
        said.append(_('A jump clears the flat ones, and only if the car is '
                      'off the ground for the whole overlap: %d ticks of '
                      'road at whatever gear you are in.') % grade.hang)
    said.append(_('The clock allows %d%% of the best line there is.')
                % int(round(100 * grade.slack)))
    spare, spare_shots = sky_toll(level, policy='gunner')
    greedy, greedy_shots = sky_toll(level, policy='sniper')
    said.append(_('Shooting only on the ticks the wheel had no use for '
                  'clears %d%% and takes %.1f out of the sky a road; '
                  'shooting the moment anything is up there, %d%% and '
                  '%.1f. Guessing clears %d%%.')
                % (int(round(100 * spare)), spare_shots,
                   int(round(100 * greedy)), greedy_shots,
                   int(round(100 * rehearse(level, policy='random')))))
    return '  '.join(said)


TWO_HANDS = TaskSpec(
    title=_('Two Hands options'),
    options=(
        Option('TWOHANDS_LEVEL', _('Level'), 3,
               values=tuple(range(1, 11))),
        Option('TWOHANDS_TRIALS', _('Roads per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('TWOHANDS_BEAT_SECONDS',
               _('Seconds a row takes in first gear'),
               0.40, values=(0.15, 0.25, 0.40, 0.60, 0.90, 1.4)),
        Option('TWOHANDS_SET_SECONDS', _('Seconds before the road moves'),
               1.2, values=(0.0, 0.4, 0.8, 1.2, 2.0, 3.0)),
        Option('TWOHANDS_ADAPTIVE', _('Climb a rung after a road driven'),
               True),
    ),
    note=two_hands_note)


def cookie_note(chosen: Dict[str, Any]) -> str:
    """What the rung gives you, and what guessing is worth.

    The floor is measured rather than derived, and it has to be: what a
    run of random presses scores here is whatever a random hand happens
    to take before the door is open far enough, which is a simulation
    question and not an arithmetic one.
    """
    from ..cookiethief import GRADES, SAFE, rehearse
    level = max(1, min(len(GRADES), int(chosen['COOKIE_LEVEL'])))
    grade = GRADES[level - 1]
    said = [_('Take %d and get out. One press is one cookie. Taken at a '
              'walk you can have %d before the door is certainly too far '
              'open, and hurrying costs you some of those.')
            % (grade.quota, grade.room)]
    said.append(_('She stands in the doorway for %d beats before she looks, '
                  'so leaving still saves you.') % grade.warn
                if grade.reactive else
                _('No warning at all at this rung: the press that opens the '
                  'door far enough is the one she sees, so the round has to '
                  'be won before there is anything to react to.'))
    said.append(_('She comes somewhere between %d and %d, and which is not '
                  'shown.') % (SAFE, grade.limit))
    if grade.gold:
        said.append(_('A golden cookie is worth %d and never comes out of '
                      'the jar, but reaching for it is two beats in which '
                      'you can neither grab nor leave.') % grade.gold)
    if grade.decoys:
        said.append(_('Somebody who is not her turns up in the doorway too.'))
    said.append(_('A cookie you got away with is worth a point and a grab '
                  'she saw costs two. Guessing gets away clean about %d%% '
                  'of the time.') % int(round(100 * rehearse(level))))
    return '  '.join(said)


COOKIE_THIEF = TaskSpec(
    title=_('Cookie Thief options'),
    options=(
        Option('COOKIE_LEVEL', _('Level'), 4,
               values=tuple(range(1, 11))),
        Option('COOKIE_TRIALS', _('Rounds per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('COOKIE_BEAT_SECONDS', _('Seconds a beat takes'),
               0.16, values=(0.08, 0.12, 0.16, 0.25, 0.40, 0.60)),
        Option('COOKIE_SET_SECONDS', _('Seconds before the first beat'),
               0.8, values=(0.0, 0.4, 0.8, 1.5, 2.5)),
        Option('COOKIE_ADAPTIVE', _('Climb a rung after a clean getaway'),
               True),
    ),
    note=cookie_note)


CHESS = TaskSpec(
    title=_('Winning Move options'),
    options=(
        Option('CHESS_LEVEL', _('Starting level'), 1,
               values=tuple(range(1, 11))),
        Option('CHESS_TRIALS', _('Puzzles per run'), 10,
               values=(1, 3, 5, 8, 10, 15, 20, 30, 50)),
        Option('CHESS_ADAPTIVE', _('Climb after a correct move'), True),
    ),
    note=lambda chosen: _('Level 1 is an obvious mate. Level 10 mixes '
                           'defenders, decoys and tactical forks. The '
                           'difficulty rises after a mate and falls after '
                           'a miss.')
)


def go_winning_move_note(chosen: Dict[str, Any]) -> str:
    """What this level actually deals, read off the ladder itself.

    Three things change as it climbs and none of them is "a bigger
    board", which is the one a player notices first. The winning move
    is *shown* on level one and never again. The group you are trying
    to kill is marked up to level four and unmarked after it, which is
    the largest single step on the ladder. And from level four the
    position carries **decoys** — points that really do capture, just
    fewer stones than the winning move takes. Past there, "did
    anything get captured" stops being the question.

    Everything below is read off
    :data:`~neural_workshop.go.DIFFICULTIES` rather than restated, so a
    note cannot drift from the ladder it is describing.
    """
    level = max(1, min(len(_GO_LADDER), int(chosen['GO_LEVEL'])))
    trials = int(chosen['GO_TRIALS'])
    rung = _GO_LADDER[level - 1]

    said = [_('Level %d: a %dx%d board, a White group of %d, %d %s a run.')
            % (level, rung.size, rung.size, rung.target_size, trials,
               _('position') if trials == 1 else _('positions'))]
    said.append(_('Black to play; one point takes its last liberty.'))
    if rung.show_move:
        said.append(_('This level points at the answer.'))
    if rung.show_target:
        said.append(_('The group to capture is marked.'))
    else:
        said.append(_('It is not marked — finding which group is '
                      'dying is most of the work.'))
    if len(rung.decoy_sizes) == 1:
        stones = rung.decoy_sizes[0]
        said.append(_('One decoy group of %d %s sits there too; '
                      'taking it captures something, not the group.')
                    % (stones, _('stone') if stones == 1 else _('stones')))
    elif rung.decoy_sizes:
        # The sizes rather than just the count, because the top
        # rungs are near ties — 23 stones against a target of 24 —
        # and that is what turns a local atari scan into a
        # whole-board comparison.
        said.append(_('%d decoy groups sit there too (%s stones); '
                      'taking any captures something, not the group.')
                    % (len(rung.decoy_sizes),
                       ', '.join(str(size)
                                 for size in rung.decoy_sizes)))
    said.append(_('The level holds for the whole run; it does not '
                  'climb after a correct answer.'))
    return ' '.join(said)


GO_WINNING_MOVE = TaskSpec(
    title=_('Find the Winning Move options'),
    options=(
        Option('GO_LEVEL', _('Level'), 1,
               values=tuple(range(1, len(_GO_LADDER) + 1))),
        Option('GO_TRIALS', _('Positions per run'), 10,
               values=(1, 3, 5, 8, 10, 15, 20, 30, 50)),
    ),
    note=go_winning_move_note)


#: Task id → the settings screen it owns.
TASK_SPECS: Dict[str, TaskSpec] = {
    'monkey_ladder': MONKEY_LADDER,
    'ncup_monte': NCUP_MONTE,
    'concentration': CONCENTRATION,
    'recognition': RECOGNITION,
    'reflex': REFLEX,
    'moving_targets': TRACKING,
    'lookout': LOOKOUT,
    'pursuit': PURSUIT,
    'out_of_sight': OUT_OF_SIGHT,
    'buzz_wire': BUZZ_WIRE,
    'donkey': DONKEY,
    'two_hands': TWO_HANDS,
    'overrun': OVERRUN,
    'count': COUNTING,
    'mr_time': MR_TIME,
    'graph_mapping': GRAPH_MAPPING,
    'matrix_reasoning': MATRIX_REASONING,
    'hidden_rule': HIDDEN_RULE,
    'jigsaw': JIGSAW,
    'video_jigsaw': VIDEO_JIGSAW,
    'camera': CAMERA,
    'sonar': SONAR,
    'dispatch': DISPATCH,
    'desktop': DESKTOP,
    'bluff': BLUFF,
    'forms': FORMS,
    'wiring': WIRING,
    'gamble': GAMBLE,
    'browser': BROWSER,
    'notebook': NOTEBOOK,
    'manual': MANUAL,
    'what_next': WHAT_NEXT,
    'triage': TRIAGE,
    'video_sequence': VIDEO_SEQUENCE,
    'tower_of_hanoi': HANOI,
    'salesman': SALESMAN,
    'sokoban': SOKOBAN,
    'maze': MAZE,
    'you_are_here': YOU_ARE_HERE,
    'sokoban_3d': SOKOBAN_3D,
    'tetris': TETRIS,
    'in_the_dark': IN_THE_DARK,
    'fog_of_war': FOG_OF_WAR,
    'removals': REMOVALS,
    'sudoku': SUDOKU,
    'n_in_a_row': NINAROW,
    'crossed_wires': CROSSED_WIRES,
    'crossword': CROSSWORD,
    'scrabble': SCRABBLE,
    'scramble': SCRAMBLE,
    'algebra': ALGEBRA,
    'numberology': NUMBEROLOGY,
    'syllogism': SYLLOGISM,
    'trivia': TRIVIA,
    'verbal_reasoning': VERBAL_REASONING,
    'marble_maze': MARBLE_MAZE,
    'chain_of_custody': CUSTODY,
    'cookie_thief': COOKIE_THIEF,
    'chess': CHESS,
    'go_winning_move': GO_WINNING_MOVE,
}


def spec_for(task_id: str) -> Optional[TaskSpec]:
    """The declarative spec for *task_id*, if it has one."""
    return TASK_SPECS.get(task_id)


def settings(spec: TaskSpec) -> Dict[str, Any]:
    """Every option in *spec*, read from the live config.

    Values the config does not hold, or holds out of range, come back
    as the option's default, so a task can use the result directly.
    """
    return {option.key: current_value(option) for option in spec.options}


def has_options(task_id: str) -> bool:
    """True when *task_id* has a settings screen ``C`` can open."""
    return task_id == 'nback' or task_id in TASK_SPECS


def open_task_options(task_id: str,
                      on_apply: Optional[ApplyCallback] = None) -> Optional[Menu]:
    """Open the settings screen for *task_id*, or return ``None``.

    The n-back workshop hands off to :class:`GameSelect`; every other
    task gets a :class:`TaskOptions` built from its spec.
    """
    if task_id == 'nback':
        if state.cfg.JAEGGI_MODE:
            return None
        from .gameselect import GameSelect
        return GameSelect()
    spec = TASK_SPECS.get(task_id)
    if spec is None:
        return None
    return TaskOptions(spec, on_apply=on_apply)
