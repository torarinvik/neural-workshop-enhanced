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
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, width_center
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


def current_value(option: Option) -> Any:
    """Read *option* from the live config, coerced into range."""
    value = state.cfg[option.key]
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
    if option.values is None:
        return bool(value)
    values = list(option.values)
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

def jigsaw_note(chosen: Dict[str, Any]) -> str:
    """What the chosen grid amounts to, and whether it can be played.

    The library line matters most: the photographs are a download the
    repository does not carry, and this screen is where a player finds
    that out before a run fails to start.
    """
    from .. import datasets
    side = int(chosen['JIGSAW_SIDE'])
    said = [_('A %dx%d puzzle is %d tiles of one photograph.')
            % (side, side, side * side)]
    if chosen['JIGSAW_ADAPTIVE']:
        said.append(_('Solve near the minimum swap count and the grid '
                      'grows; flail and it shrinks.'))
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
        Option('JIGSAW_SIDE', _('Tiles per side'), 3,
               values=(2, 3, 4, 5, 6, 7, 8, 10)),
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
    title=_('You Are Here options'),
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


def cookie_note(chosen: Dict[str, Any]) -> str:
    """What the rung does to the boy, and what guessing is worth.

    The floor is measured rather than derived, and it has to be: what a
    run of random presses scores here is whatever a random walk in
    speed happens to eat before somebody walks in, which is a
    simulation question and not an arithmetic one.
    """
    from ..cookiethief import GRADES, rehearse
    level = max(1, min(len(GRADES), int(chosen['COOKIE_LEVEL'])))
    grade = GRADES[level - 1]
    said = [_('Take %d, with none of them seen. Flat out he needs %d beats '
              'to stop and she gives him %d.')
            % (grade.quota, grade.stopping, grade.warn)]
    said.append(_('Braking the moment she appears is enough at this rung.')
                if grade.reactive else
                _('Braking the moment she appears is not enough at this '
                  'rung: he still gets %d out of the jar under her eye, so '
                  'the round has to be won before there is anything to '
                  'react to.') % grade.reflex_bites)
    if grade.gold:
        said.append(_('A golden cookie is worth %d and never comes out of '
                      'the jar, but reaching for it costs two beats with no '
                      'brake.') % grade.gold)
    if grade.decoys:
        said.append(_('Somebody who is not her turns up in the doorway too.'))
    said.append(_('A cookie he got away with is worth a point and one she '
                  'saw costs three. Guessing gets away clean about %d%% of '
                  'the time.') % int(round(100 * rehearse(level))))
    return '  '.join(said)


COOKIE_THIEF = TaskSpec(
    title=_('Cookie Thief options'),
    options=(
        Option('COOKIE_LEVEL', _('Level'), 4,
               values=tuple(range(1, 11))),
        Option('COOKIE_TRIALS', _('Rounds per run'), 5,
               values=(1, 2, 3, 5, 8, 10, 15, 20)),
        Option('COOKIE_BEAT_SECONDS', _('Seconds a beat takes'),
               0.35, values=(0.12, 0.20, 0.35, 0.50, 0.75, 1.2)),
        Option('COOKIE_SET_SECONDS', _('Seconds before the first beat'),
               0.9, values=(0.0, 0.4, 0.9, 1.5, 2.5)),
        Option('COOKIE_ADAPTIVE', _('Climb a rung after a clean getaway'),
               True),
    ),
    note=cookie_note)


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
    'count': COUNTING,
    'graph_mapping': GRAPH_MAPPING,
    'matrix_reasoning': MATRIX_REASONING,
    'jigsaw': JIGSAW,
    'tower_of_hanoi': HANOI,
    'salesman': SALESMAN,
    'sokoban': SOKOBAN,
    'maze': MAZE,
    'you_are_here': YOU_ARE_HERE,
    'in_the_dark': IN_THE_DARK,
    'fog_of_war': FOG_OF_WAR,
    'removals': REMOVALS,
    'sudoku': SUDOKU,
    'crossed_wires': CROSSED_WIRES,
    'chain_of_custody': CUSTODY,
    'cookie_thief': COOKIE_THIEF,
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
