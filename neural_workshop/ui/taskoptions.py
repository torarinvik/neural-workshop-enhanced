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

#: Task id → the settings screen it owns.
TASK_SPECS: Dict[str, TaskSpec] = {
    'monkey_ladder': MONKEY_LADDER,
    'ncup_monte': NCUP_MONTE,
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
