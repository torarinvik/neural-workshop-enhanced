# -*- coding: utf-8 -*-
"""Widgets that belong to a trial in progress.

The feedback labels along the bottom edge are the player's controls:
each names the key that reports a match for one modality, and colours
itself according to whether the press was right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from decimal import Decimal
from typing import List

import pyglet
from pyglet.window import key

from .. import state
from ..constants import CLINICAL_MODE
from ..config import get_threshold_advance, get_threshold_fallback
from ..gamemode import get_color
from ..geometry import (calc_fontsize, from_bottom_edge, from_left_edge,
                        from_right_edge, scale_to_width, width_center)
from ..grid import (current_active_position_ids, current_cell_count,
                    current_grid_size)
from ..matching import CORRECT, INCORRECT, MISSED, UNKNOWN, check_match
from ..timing import trial_interval_ms
from ..i18n import _


class FeedbackLabel:
    """One "K: position match" prompt, coloured by the player's answer."""

    def __init__(self, modality: str, pos: int = 0, total: int = 1) -> None:
        """Build the label for *modality*.

        *pos* is this label's position left-to-right and *total* the
        number of labels in this mode; together they set the spacing.
        """
        cfg, mode = state.cfg, state.mode
        self.modality = modality
        self.letter = key.symbol_string(cfg['KEY_%s' % modality.upper()])
        if self.letter == 'SEMICOLON':
            self.letter = ';'

        self.mousetext = self._mouse_prefix(pos, total)
        self.text = '%s %s: %s' % (_(self.mousetext), self.letter,
                                   _(self._modality_name(modality)))
        font_size = self._font_size(total)
        if total < 4:
            self.text += _(' match')

        self.label = pyglet.text.Label(
            text=self.text,
            # x is fixed up below, once the label's width is known.
            x=-200, y=from_bottom_edge(30),
            anchor_x='left', anchor_y='center', batch=state.batch,
            font_size=font_size)

        # pyglet does not expose a laid-out label's width before drawing,
        # so estimate it from the character count.
        width = (len(self.text) * font_size * 4) / 5
        spacing = (state.window.width - 100) / float(total - .99)
        x = 30 + int(pos * spacing - width * pos / (total - .5))

        self.icon = None
        if mode.flags[mode.mode]['multi'] > 1 and modality[-1].isdigit():
            x = self._build_icon(int(modality[-1]), x)
        self.label.x = x
        self.update()

    @staticmethod
    def _modality_name(modality: str) -> str:
        """Human-readable name; the combination modes cross channels."""
        if modality.endswith('vis'):
            return modality[:-3] + ' & n-vis'
        if modality.endswith('audio') and modality != 'audio':
            return modality[:-5] + ' & n-audio'
        if (state.mode.flags[state.mode.mode]['multi'] == 1
                and modality == 'position1'):
            return 'position'
        return modality

    @staticmethod
    def _mouse_prefix(pos: int, total: int) -> str:
        """Dual n-back can be played with the mouse; say so."""
        if total != 2 or state.cfg.JAEGGI_MODE or not state.cfg.ENABLE_MOUSE:
            return ''
        return 'Left-click or' if pos == 0 else 'Right-click or'

    @staticmethod
    def _font_size(total: int) -> float:
        if total < 4:
            return calc_fontsize(16)
        if total < 5:
            return calc_fontsize(14)
        if total < 6:
            return calc_fontsize(13)
        return calc_fontsize(11)

    def _build_icon(self, stimulus_id: int, x: int) -> int:
        """Draw the multi-stim marker beside the label; return the new x."""
        self.id = stimulus_id
        visual = state.visuals[stimulus_id - 1]
        if state.cfg.MULTI_MODE == 'color':
            color_index = state.cfg.VISUAL_COLORS[stimulus_id - 1] - 1
            self.icon = pyglet.sprite.Sprite(
                visual.spr_square[color_index].image)
            self.icon.scale = .125 * visual.size / visual.image_set_size
            self.icon.y = from_bottom_edge(22)
            self.icon.x = x - 15
            x += 15
        else:  # 'image'
            self.icon = pyglet.sprite.Sprite(
                visual.images[stimulus_id - 1].image)
            self.icon.color = tuple(get_color(1)[:3])
            self.icon.scale = .25 * visual.size / visual.image_set_size
            self.icon.y = from_bottom_edge(15)
            self.icon.x = x - 25
            x += 25
        self.icon.opacity = 255
        self.icon.batch = state.batch
        return x

    def draw(self) -> None:
        """The label is in the batch; nothing to do here."""

    def update(self) -> None:
        """Refresh the text and colour from the player's current answer."""
        cfg, mode = state.cfg, state.mode
        if (mode.started and not mode.hide_text
                and self.modality in mode.modalities[mode.mode]):
            self.label.text = self.text
        else:
            self.label.text = ''

        if cfg.SHOW_FEEDBACK and mode.inputs[self.modality]:
            result = check_match(self.modality)
            if result == CORRECT:
                self.label.color = cfg.COLOR_LABEL_CORRECT
            elif result == UNKNOWN:
                self.label.color = cfg.COLOR_LABEL_OOPS
            elif result == INCORRECT:
                self.label.color = cfg.COLOR_LABEL_INCORRECT
        elif (cfg.SHOW_FEEDBACK and not mode.inputs['audiovis']
                and mode.show_missed):
            if check_match(self.modality, check_missed=True) == MISSED:
                self.label.color = cfg.COLOR_LABEL_OOPS
        else:
            self.label.color = cfg.COLOR_TEXT
            self.label.weight = 'normal'

    def delete(self) -> None:
        self.label.delete()
        if self.icon is not None:
            self.icon.batch = None


def generate_input_labels() -> List[FeedbackLabel]:
    """One feedback label per modality of the current mode."""
    modalities = state.mode.modalities[state.mode.mode]
    total = len(modalities)
    return [FeedbackLabel(m, pos, total)
            for pos, m in enumerate(modalities) if m != 'arithmetic']


class ArithmeticAnswerLabel:
    """The number the player is typing in arithmetic mode."""

    def __init__(self) -> None:
        self.answer: List[str] = []
        self.negative = False
        self.decimal = False
        self.label = pyglet.text.Label(
            '', x=state.window.width / 2 - 40, y=from_bottom_edge(30),
            anchor_x='left', anchor_y='center', batch=state.batch)
        self.update()

    def update(self) -> None:
        cfg, mode = state.cfg, state.mode
        if 'arithmetic' not in mode.modalities[mode.mode] or not mode.started \
                or mode.hide_text:
            self.label.text = ''
            return

        self.label.font_size = calc_fontsize(16)
        self.label.text = _('Answer: ') + str(self.parse_answer())

        if cfg.SHOW_FEEDBACK and mode.show_missed:
            result = check_match('arithmetic')
            if result == CORRECT:
                self.label.color = cfg.COLOR_LABEL_CORRECT
                self.label.weight = 'bold'
            elif result == INCORRECT:
                self.label.color = cfg.COLOR_LABEL_INCORRECT
                self.label.weight = 'bold'
        else:
            self.label.color = cfg.COLOR_TEXT
            self.label.weight = 'normal'

    def parse_answer(self) -> Decimal:
        """The typed digits as a number; empty reads as zero."""
        chars = ''.join(self.answer)
        result = Decimal('0') if chars in ('', '.') else Decimal(chars)
        return -result if self.negative else result

    def input(self, char: str) -> None:
        """Append one typed character, honouring sign and decimal point."""
        if char == '-':
            self.negative = not self.negative
        elif char == '.':
            if not self.decimal:
                self.decimal = True
                self.answer.append(char)
        else:
            self.answer.append(char)
        self.update()

    def reset_input(self) -> None:
        self.answer = []
        self.negative = False
        self.decimal = False
        self.update()


class SessionInfoLabel:
    """Trial timing, session length and board size, bottom left."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', multiline=True, width=scale_to_width(128),
            font_size=calc_fontsize(11), color=state.cfg.COLOR_TEXT,
            x=from_left_edge(20), y=from_bottom_edge(145),
            anchor_x='left', anchor_y='top', batch=state.batch)
        self.update()

    def update(self) -> None:
        mode = state.mode
        if mode.started or CLINICAL_MODE:
            self.label.text = ''
            return
        n = current_grid_size()
        ms = trial_interval_ms()
        if ms < 1000:
            timing = _('%i ms/trial') % ms
        else:
            timing = _('%1.2f sec/trial') % (ms / 1000.0)
        session_s = int((ms / 1000.0) * mode.num_trials_total)

        ncells = current_cell_count()
        active = current_active_position_ids()
        if len(active) < ncells:
            gridline = _('Grid %i×%i (%i/%i cells)') % (n, n, len(active),
                                                        ncells)
        else:
            gridline = _('Grid %i×%i') % (n, n)
        self.label.text = _('Session:\n%s\n%i+%i trials\n%i seconds\n%s') % (
            timing, mode.num_trials,
            mode.num_trials_total - mode.num_trials, session_s, gridline)

    def flash(self) -> None:
        pyglet.clock.unschedule(self.unflash)
        self.label.weight = 'bold'
        self.update()
        pyglet.clock.schedule_once(self.unflash, 1.0)

    def unflash(self, dt: float) -> None:
        self.label.weight = 'normal'
        self.update()


class ThresholdLabel:
    """The score thresholds for moving up or down a level, bottom right."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', multiline=True, width=scale_to_width(128),
            font_size=calc_fontsize(11), color=state.cfg.COLOR_TEXT,
            x=from_right_edge(20), y=from_bottom_edge(145),
            anchor_x='right', anchor_y='top', batch=state.batch)
        self.update()

    def update(self) -> None:
        mode = state.mode
        if mode.started or mode.manual or CLINICAL_MODE:
            self.label.text = ''
        else:
            self.label.text = _('Thresholds:\nRaise level: ≥ %i%%\n'
                                'Lower level: < %i%%') % (
                get_threshold_advance(), get_threshold_fallback())


class SpaceLabel:
    """The "press SPACE to begin session #N" prompt."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(16), weight='bold',
            color=(32, 32, 255, 255), x=width_center(),
            y=from_bottom_edge(62), anchor_x='center', anchor_y='center',
            batch=state.batch)
        self.update()

    def update(self) -> None:
        mode = state.mode
        if mode.started:
            self.label.text = ''
            return
        parts = [_('Press SPACE to begin session #'),
                 str(mode.session_number + 1), ': ',
                 mode.long_mode_names[mode.mode] + ' ']
        if state.cfg.VARIABLE_NBACK:
            parts.append(_('V. '))
        parts.append(str(mode.back))
        parts.append(_('-Back'))
        if mode.mode == 10:
            parts.append(_(' (%i/%i cells, %i trials)')
                         % (len(current_active_position_ids()),
                            current_cell_count(), mode.num_trials_total))
        self.label.text = ''.join(parts)
