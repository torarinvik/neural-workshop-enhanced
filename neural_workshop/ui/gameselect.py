# -*- coding: utf-8 -*-
"""The game-mode screen.

The player ticks the modalities they want; :meth:`GameSelect.calc_mode`
searches the mode tables for the one mode whose modality set matches
exactly, then adds the bits for the crab / multi-stim / self-paced
variants. Not every combination exists, hence "invalid mode".

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, List, Union

import pyglet

from .. import state
from ..geometry import width_center
from ..grid import (current_active_cell_limit, current_cell_count,
                    current_grid_bounds, current_grid_size)
from ..timing import set_trial_interval_ms, trial_interval_ms
from .menu import BLANK_LINE, AllCycler, Cycler, Menu, PercentCycler
from ..i18n import _

#: Modalities the player can switch on directly.
_MODALITIES: List[str] = ['position1', 'color', 'image', 'audio', 'audio2',
                          'arithmetic']

#: Selectable trial lengths, in milliseconds.
_TRIAL_MS_VALUES: List[int] = [1, 2, 5, 10, 16, 20, 25, 33, 50, 75, 100, 150,
                               200, 250, 333, 500, 750, 1000, 1500, 2000,
                               2500, 3000, 4000, 5000]

#: Selectable curriculum caps on the number of active cells; 0 means all.
_CELL_VALUES: List[int] = [0, 2, 3, 4, 6, 8, 12, 16, 24, 32, 64]


def _cycler_with(values: List[Any], current: Any,
                 fallback: Any, factory: type = Cycler) -> Cycler:
    """A Cycler over *values*, extended so *current* is always selectable."""
    values = list(values)
    if current not in values:
        values.append(current)
        values.sort()
    try:
        default = values.index(current)
    except ValueError:
        default = values.index(fallback) if fallback in values else 0
    return factory(values=values, default=default)


class GameSelect(Menu):
    """Choose modalities, board size, timing and mode variants."""

    def __init__(self) -> None:
        cfg = state.cfg
        mode = state.mode
        options = list(_MODALITIES)
        options.extend([BLANK_LINE, 'combination', BLANK_LINE, 'variable',
                        'crab', BLANK_LINE, 'grid', 'active_cells',
                        'trial_ms', BLANK_LINE, 'multi', 'multimode',
                        BLANK_LINE, 'selfpaced', BLANK_LINE, 'interference'])

        names = {m: _('Use %s') % m for m in _MODALITIES}
        names['position1'] = _('Use position')
        names['combination'] = _('Combination N-back mode')
        names['variable'] = _('Use variable N-Back levels')
        names['grid'] = _('Grid size')
        names['active_cells'] = _('Active position cells')
        names['trial_ms'] = _('Trial interval (ms)')
        names['crab'] = _('Crab-back mode (reverse order of sets of N stimuli)')
        names['multi'] = _('Simultaneous visual stimuli')
        names['multimode'] = _('Simultaneous stimuli differentiated by')
        names['selfpaced'] = _('Self-paced mode')
        names['interference'] = _('Interference (tricky stimulus generation)')

        curmodes = mode.modalities[mode.mode]
        values: Dict[str, Any] = {op: None for op in options}
        for m in _MODALITIES:
            values[m] = m in curmodes
        values['combination'] = 'visvis' in curmodes
        values['variable'] = bool(cfg.VARIABLE_NBACK)
        values['crab'] = bool(mode.flags[mode.mode]['crab'])
        values['selfpaced'] = bool(mode.flags[mode.mode]['selfpaced'])
        values['multi'] = Cycler(values=[1, 2, 3, 4],
                                 default=mode.flags[mode.mode]['multi'] - 1)
        values['multimode'] = Cycler(values=['color', 'image'],
                                     default=cfg.MULTI_MODE)

        interference = [i / 8. for i in range(0, 9)]
        values['interference'] = _cycler_with(
            interference, cfg.CHANCE_OF_INTERFERENCE,
            cfg.DEFAULT_CHANCE_OF_INTERFERENCE, PercentCycler)

        gmin, gmax = current_grid_bounds()
        values['grid'] = _cycler_with(list(range(gmin, gmax + 1)),
                                      current_grid_size(), 3)
        values['trial_ms'] = _cycler_with(_TRIAL_MS_VALUES,
                                          trial_interval_ms(), 3000)
        cell_values = list(_CELL_VALUES)
        if current_cell_count() not in cell_values:
            cell_values.append(current_cell_count())
            cell_values.sort()
        values['active_cells'] = _cycler_with(
            cell_values, current_active_cell_limit(), 0, AllCycler)

        Menu.__init__(self, options, values, names=names,
                      title=_('Choose your game mode'))
        self.modelabel = pyglet.text.Label(
            '', font_size=self.titlesize, weight='normal',
            color=(0, 0, 0, 255), batch=self.batch,
            x=width_center(), y=(state.window.height * 1) / 10,
            anchor_x='center', anchor_y='center')
        self.newmode: Union[int, bool] = mode.mode
        self.update_labels()

    # --- mode resolution -------------------------------------------------

    def update_labels(self) -> None:
        self.calc_mode()
        try:
            if self.newmode:
                self.modelabel.text = (
                    state.mode.long_mode_names[self.newmode]
                    + (' V.' if self.values['variable'] else '') + ' N-Back')
            else:
                self.modelabel.text = _('An invalid mode has been selected.')
        except AttributeError:
            pass  # called from Menu.__init__, before modelabel exists
        Menu.update_labels(self)

    def _selected_modalities(self) -> List[str]:
        """The modality names the current tick-boxes imply."""
        modes = [k for k, v in self.values.items()
                 if v and not isinstance(v, Cycler)]
        for name in ('variable', 'crab', 'selfpaced'):
            if name in modes:
                modes.remove(name)
        if 'combination' in modes:
            modes.remove('combination')
            # 'audio' is already present in every combination mode.
            modes.extend(['visvis', 'visaudio', 'audiovis'])
        return modes

    def _variant_bits(self) -> int:
        bits = 256 * (self.values['multi'].value() - 1)
        if self.values['crab']:
            bits += 128
        if self.values['selfpaced']:
            bits += 1024
        return bits

    def calc_mode(self) -> None:
        """Resolve the tick-boxes to a mode number, or ``False``."""
        wanted = set(self._selected_modalities())
        candidates = {k for k, v in state.mode.modalities.items()
                      if set(v) == wanted}
        candidates &= set(range(0, 128))
        if len(candidates) != 1:
            self.newmode = False
            return
        candidate = candidates.pop() + self._variant_bits()
        self.newmode = (candidate if candidate in state.mode.modalities
                        else False)

    # --- lifecycle -------------------------------------------------------

    def save(self) -> None:
        cfg = state.cfg
        self.calc_mode()
        cfg.VARIABLE_NBACK = self.values['variable']
        cfg.MULTI_MODE = self.values['multimode'].value()
        cfg.CHANCE_OF_INTERFERENCE = self.values['interference'].value()
        cfg.GRID_SIZE = int(self.values['grid'].value())
        state.field.rebuild_grid()
        for visual in state.visuals:
            visual.sync_size()
        set_trial_interval_ms(int(self.values['trial_ms'].value()))
        cfg.ACTIVE_POSITION_CELLS = int(self.values['active_cells'].value())
        cfg.POSITION_CELL_COUNT = cfg.ACTIVE_POSITION_CELLS
        if self.newmode:
            state.mode.mode = self.newmode

    def close(self) -> None:
        from ..session import update_all_labels
        from ..timing import apply_trial_interval_override
        Menu.close(self)
        if not state.mode.manual:
            state.mode.enforce_standard_mode()
            state.stats.retrieve_progress()
        apply_trial_interval_override()
        update_all_labels()
        state.circles.update()

    # --- option interlocks ----------------------------------------------

    def _apply_interlocks(self, choice: str) -> None:
        """Keep mutually exclusive options from being on at once."""
        values = self.values
        if choice == 'combination':
            values['arithmetic'] = False
            values['image'] = False
            values['audio2'] = False
            values['audio'] = True
            values['multi'].i = 0
        elif choice == 'arithmetic':
            values['image'] = False
            values['audio'] = False
            values['audio2'] = False
            values['combination'] = False
            values['multi'].i = 0
        elif choice == 'audio':
            values['arithmetic'] = False
            if values['audio']:
                values['combination'] = False
                values['audio2'] = False
        elif choice == 'audio2':
            values['audio'] = True
            values['combination'] = False
            values['arithmetic'] = False
        elif choice == 'image':
            values['combination'] = False
            values['arithmetic'] = False
            if values['multi'].value() > 1 and not values['image']:
                values['color'] = False
                values['multimode'].choose('color')
        elif choice == 'color':
            if values['multi'].value() > 1 and not values['color']:
                values['image'] = False
                values['multimode'].choose('image')
        elif choice == 'multi':
            values['arithmetic'] = False
            values['combination'] = False
            values[values['multimode'].value()] = False
        elif choice == 'multimode' and values['multi'].value() > 1:
            previous = values['multimode'].value()
            other = 'color' if previous == 'image' else 'image'
            values[previous] = values[other]
            values[other] = False

    def select(self) -> None:
        self._apply_interlocks(self.options[self.selpos])
        Menu.select(self)
        # Never leave the player with nothing to match.
        enabled = [k for k, v in self.values.items() if v]
        substantive = [v for k, v in self.values.items()
                       if v and k not in ('crab', 'combination', 'variable')]
        if not substantive or (len(enabled) == 1
                               and enabled[0] in ('image', 'color')):
            self.values['position1'] = True
            self.update_labels()
        self.calc_mode()
