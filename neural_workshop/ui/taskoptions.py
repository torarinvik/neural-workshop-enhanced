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

from .. import state
from .menu import Cycler, Menu
from ..i18n import _

#: Called after a task's options are applied, so the task can restart.
ApplyCallback = Callable[[], None]


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
    """A task's settings screen: a title and the rows it shows."""

    title: str
    options: Sequence[Option]


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
                      footnote=_('Esc: cancel     Space: modify option'
                                 '     Enter: apply'))

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
               values=(3, 4, 5, 6, 7, 8)),
        Option('MONKEY_LADDER_START_LENGTH', _('Starting sequence length'), 3,
               values=(2, 3, 4, 5, 6, 7, 8, 9, 10, 12)),
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
               values=(3, 4, 5, 6, 7, 8)),
        Option('NCUP_MONTE_MAX_CUPS', _('Maximum number of cups'), 8,
               values=(3, 4, 5, 6, 7, 8, 10, 12)),
        Option('NCUP_MONTE_ADAPTIVE',
               _('Adapt the cup count to your performance'), True),
        Option('NCUP_MONTE_SWAPS', _('Swaps per round (plus one per cup)'), 6,
               values=(2, 4, 6, 8, 12, 16, 24, 32)),
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
               values=(4, 6, 8, 10, 12, 15, 18, 21, 24, 30)),
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
               values=(10, 20, 30, 40, 60, 80, 100, 150)),
        Option('RECOGNITION_MEDIUM', _('Present'), 'image',
               values=('image', 'sound')),
        Option('RECOGNITION_REPEAT_PERCENT', _('Share of items repeated'), 40,
               values=(20, 30, 40, 50), suffix='%'),
        Option('RECOGNITION_MIN_LAG', _('Smallest gap before a repeat'), 4,
               values=(1, 2, 3, 4, 6, 8, 12, 20, 30), suffix=' items'),
        Option('RECOGNITION_STUDY_MS', _('Hide the image after'), 0,
               values=(0, 500, 1000, 1500, 2000, 3000), suffix=' ms'),
        Option('RECOGNITION_FEEDBACK', _('Say whether each answer was right'),
               True),
    ))

REFLEX = TaskSpec(
    title=_('Reflex options'),
    options=(
        Option('REFLEX_TARGETS', _('Targets per run'), 40,
               values=(10, 20, 30, 40, 60, 80, 120, 200)),
        Option('REFLEX_LIFETIME_MS', _('A target takes this long to vanish'),
               1600, values=(400, 600, 800, 1200, 1600, 2200, 3000, 4000),
               suffix=' ms'),
        Option('REFLEX_SPAWN_MS', _('Gap between targets appearing'), 700,
               values=(150, 250, 400, 550, 700, 1000, 1500, 2000),
               suffix=' ms'),
        Option('REFLEX_MAX_ACTIVE', _('Most targets on screen at once'), 3,
               values=(1, 2, 3, 4, 5, 6, 8)),
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
               values=(2, 4, 6, 8, 10, 12, 16, 20, 25, 30)),
        Option('COUNT_TRIALS', _('Trials per run'), 15,
               values=(5, 10, 15, 20, 30, 50)),
        Option('COUNT_EXPOSURE_MS', _('Hide the shapes after'), 0,
               values=(0, 200, 350, 500, 750, 1000, 2000, 4000),
               suffix=' ms'),
        Option('COUNT_ADAPTIVE', _('Add a shape when right, drop one when wrong'),
               True),
        Option('COUNT_SHOW_ANSWER', _('Show the true count after each trial'),
               True),
    ))

GRAPH_MAPPING = TaskSpec(
    title=_('Graph Mapping options'),
    options=(
        Option('GRAPH_MAP_NODES', _('Dots to start with'), 6,
               values=(4, 5, 6, 7, 8, 9, 10)),
        Option('GRAPH_MAP_DENSITY', _('How many connections'), 'medium',
               values=('sparse', 'medium', 'dense')),
        Option('GRAPH_MAP_TRIALS', _('Pairs per run'), 20,
               values=(5, 10, 15, 20, 30, 50)),
        Option('GRAPH_MAP_SUBTLE',
               _('Mismatches keep every connection count the same'), True),
        Option('GRAPH_MAP_EXPOSURE_MS', _('Hide the graphs after'), 0,
               values=(0, 3000, 5000, 8000, 12000, 20000), suffix=' ms'),
        Option('GRAPH_MAP_ADAPTIVE',
               _('Add a dot when right, drop one when wrong'), True),
        Option('GRAPH_MAP_FEEDBACK', _('Say whether each answer was right'),
               True),
    ))

#: Task id → the settings screen it owns.
TASK_SPECS: Dict[str, TaskSpec] = {
    'monkey_ladder': MONKEY_LADDER,
    'ncup_monte': NCUP_MONTE,
    'concentration': CONCENTRATION,
    'recognition': RECOGNITION,
    'reflex': REFLEX,
    'count': COUNTING,
    'graph_mapping': GRAPH_MAPPING,
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
