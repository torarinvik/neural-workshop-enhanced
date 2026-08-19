# -*- coding: utf-8 -*-
"""Persistent on-screen furniture: title, key list, logo and notices.

Each class owns one pyglet label (or a small group) and knows how to
refresh it from the current game state. Labels that belong to the batch
are drawn automatically; the ones with a ``draw`` method are drawn
explicitly by :func:`neural_workshop.events.on_draw`, because they only
appear on some screens.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Tuple

import pyglet

import bwaccel

from .. import state
from ..constants import CLINICAL_MODE, VERSION
from ..geometry import (calc_fontsize, from_bottom_edge, from_left_edge,
                        from_top_edge, from_width_center, scale_to_height,
                        scale_to_width, width_center)
from ..grid import current_active_position_ids, current_cell_count
from ..i18n import _


class Circles:
    """The three-strikes indicator in the top left corner."""

    def __init__(self) -> None:
        self.y = from_top_edge(20)
        self.start_x = from_left_edge(30)
        self.radius = scale_to_width(8)
        self.distance = scale_to_width(20)

        dim = 64 if state.cfg.BLACK_BACKGROUND else 192
        self.not_activated: Tuple[int, int, int, int] = (dim, dim, dim, 255)
        self.activated: Tuple[int, int, int, int] = (64, 64, 255, 255)
        self.invisible: Tuple[int, int, int, int] = (
            (0, 0, 0, 0) if state.cfg.BLACK_BACKGROUND else (255, 255, 255, 0))

        self.circle: List[pyglet.shapes.Circle] = [
            pyglet.shapes.Circle(self.start_x + self.distance * index, self.y,
                                 self.radius, color=self.not_activated,
                                 batch=state.batch)
            for index in range(state.cfg.THRESHOLD_FALLBACK_SESSIONS - 1)]
        self.update()

    def update(self) -> None:
        """One filled circle per session already passed at this level."""
        mode = state.mode
        if mode.manual or mode.started or state.cfg.JAEGGI_MODE:
            for circle in self.circle:
                circle.color = self.invisible
            return
        for index, circle in enumerate(self.circle):
            circle.color = (self.activated if index < mode.progress
                            else self.not_activated)


class UpdateLabel:
    """Notice that a newer release is available."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', multiline=True, width=state.field.size // 3 - 4,
            align='middle', font_size=calc_fontsize(11), weight='bold',
            color=(0, 128, 0, 255), x=width_center(),
            y=state.field.center_x + state.field.size // 6,
            anchor_x='center', anchor_y='center', batch=state.batch)
        self.update()

    def update(self) -> None:
        if not state.mode.started and state.update_available:
            self.label.text = (_('An update is available (')
                               + str(state.update_version)
                               + _('). Press W to open web site'))
        else:
            self.label.text = ''


class GameModeLabel:
    """The mode and level caption above the field."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(16), color=state.cfg.COLOR_TEXT,
            x=width_center(), y=from_top_edge(20),
            anchor_x='center', anchor_y='center', batch=state.batch)
        self.update()

    def update(self) -> None:
        mode = state.mode
        if mode.started and mode.hide_text:
            self.label.text = ''
            return
        parts: List[str] = []
        if state.cfg.JAEGGI_MODE and not CLINICAL_MODE:
            parts.append(_('Jaeggi mode: '))
        if mode.manual:
            parts.append(_('Manual mode: '))
        if state.cfg.GRID_3D:
            parts.append(_('3D '))
        parts.append(mode.long_mode_names[mode.mode] + ' ')
        if state.cfg.VARIABLE_NBACK:
            parts.append(_('V. '))
        parts.append(str(mode.back))
        parts.append(_('-Back'))
        if mode.mode == 10:
            parts.append(_(' (%i/%i cells, %i trials)')
                         % (len(current_active_position_ids()),
                            current_cell_count(), mode.num_trials_total))
        self.label.text = ''.join(parts)

    def flash(self) -> None:
        """Briefly tint the caption to acknowledge a change."""
        pyglet.clock.unschedule(self.unflash)
        self.label.color = (255, 0, 255, 255)
        self.update()
        pyglet.clock.schedule_once(self.unflash, 0.5)

    def unflash(self, dt: float) -> None:
        self.label.color = state.cfg.COLOR_TEXT
        self.update()


class JaeggiWarningLabel:
    """Explains why a mode key did nothing while Jaeggi mode is on."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(12), weight='bold',
            color=(255, 0, 255, 255), x=width_center(),
            y=state.field.center_x + state.field.size // 3 + 8,
            anchor_x='center', anchor_y='center', batch=state.batch)

    def show(self) -> None:
        pyglet.clock.unschedule(self.hide)
        self.label.text = _('Please disable Jaeggi Mode to access '
                            'additional modes.')
        pyglet.clock.schedule_once(self.hide, 3.0)

    def hide(self, dt: float) -> None:
        self.label.text = ''


class KeysListLabel:
    """The keyboard reference down the left-hand side."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', multiline=True, width=scale_to_width(300), weight='normal',
            font_size=calc_fontsize(9), color=state.cfg.COLOR_TEXT,
            x=scale_to_width(10), y=from_top_edge(30),
            anchor_x='left', anchor_y='top', batch=state.batch)
        self.update()

    def _in_session_keys(self) -> List[str]:
        if state.mode.hide_text:
            return []
        return [_('P: Pause / Unpause\n'), '\n',
                _('F8: Hide / Reveal Text\n'), '\n',
                _('ESC: Cancel Session\n')]

    def _hub_keys(self) -> List[str]:
        cfg, mode = state.cfg, state.mode
        parts: List[str] = []
        if 'morse' in cfg.AUDIO1_SETS or 'morse' in cfg.AUDIO2_SETS:
            parts.extend([_('J: Morse Code Reference\n'), '\n'])
        parts.extend([_('H: Help / Tutorial\n'), '\n'])
        if mode.manual:
            parts.extend([
                _('F1: Decrease N-Back\n'), _('F2: Increase N-Back\n'), '\n',
                _('F3: Decrease Trials\n'), _('F4: Increase Trials\n'), '\n',
                _('F5: Decrease Speed\n'), _('F6: Increase Speed\n'), '\n',
                _('C: Choose Game Type\n'), _('S: Select Sounds\n')])
        parts.append(_('I: Select Images\n'))
        if mode.manual:
            parts.append(_('M: Standard Mode\n'))
        else:
            parts.extend([
                _('M: Manual Mode\n'), _('D: Donate\n'), '\n',
                _('G: Daily Progress Graph\n'), '\n',
                _('W: Brain Workshop Web Site\n')])
        if cfg.WINDOW_FULLSCREEN:
            parts.append(_('E: Saccadic Eye Exercise\n'))
        parts.extend(['\n', _('F11: Full Screen\n'),
                      _('ESC: Task menu\n')])
        return parts

    def update(self) -> None:
        mode = state.mode
        if mode.started:
            self.label.y = from_top_edge(30)
            parts = self._in_session_keys()
        elif CLINICAL_MODE:
            self.label.y = from_top_edge(30)
            parts = [_('ESC: Exit')]
        else:
            self.label.y = from_top_edge(
                30 if (mode.manual or state.cfg.JAEGGI_MODE) else 40)
            parts = self._hub_keys()
        self.label.text = ''.join(parts)


class TitleMessageLabel:
    """Product name, version and native-backend tag on the title screen."""

    def __init__(self) -> None:
        color = state.cfg.COLOR_TEXT
        self.label = pyglet.text.Label(
            _('Neural Workshop'), font_size=calc_fontsize(32), weight='bold',
            color=color, x=width_center(), y=from_top_edge(25),
            anchor_x='center', anchor_y='center')
        self.label2 = pyglet.text.Label(
            _('Version ') + str(VERSION), font_size=calc_fontsize(14),
            weight='normal', color=color, x=width_center(),
            y=from_top_edge(55), anchor_x='center', anchor_y='center')
        self.native = pyglet.text.Label(
            bwaccel.banner(), font_size=calc_fontsize(10), weight='normal',
            color=color, x=width_center(), y=from_top_edge(78),
            anchor_x='center', anchor_y='center')

    def draw(self) -> None:
        self.label.draw()
        self.label2.draw()
        self.native.draw()


class TitleKeysLabel:
    """The key list and "press space" prompt on the title screen."""

    def __init__(self) -> None:
        cfg = state.cfg
        parts: List[str] = []
        if not (cfg.JAEGGI_MODE or CLINICAL_MODE):
            parts.extend([_('SPACE: Task menu\n'),
                          _('C: Choose N-Back mode\n'),
                          _('S: Choose Sounds\n'),
                          _('I: Choose Images\n')])
        if not CLINICAL_MODE:
            parts.extend([_('U: Choose User\n'),
                          _('G: Daily Progress Graph\n')])
        parts.append(_('F11: Full Screen\n'))
        parts.append(_('H: Help / Tutorial\n'))
        if not CLINICAL_MODE:
            parts.extend([_('D: Donate\n'),
                          _('F: Go to Forum / Mailing List\n'),
                          _('O: Edit configuration file')])

        self.keys = pyglet.text.Label(
            ''.join(parts), multiline=True, width=scale_to_width(260),
            font_size=calc_fontsize(12), weight='bold', color=cfg.COLOR_TEXT,
            x=from_width_center(65), y=from_bottom_edge(260),
            anchor_x='center', anchor_y='top')
        self.space = pyglet.text.Label(
            _('Press SPACE to enter the Workshop'), font_size=calc_fontsize(20),
            weight='bold', color=(32, 32, 255, 255), x=width_center(),
            y=from_bottom_edge(35), anchor_x='center', anchor_y='center')

    def draw(self) -> None:
        self.space.draw()
        self.keys.draw()


class NativeBackendLabel:
    """Tiny ``native: C`` / ``native: Python`` tag on the workshop hub."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(9), color=state.cfg.COLOR_TEXT,
            x=from_left_edge(10), y=from_bottom_edge(14),
            anchor_x='left', anchor_y='center', batch=state.batch)
        self.update()

    def update(self) -> None:
        if CLINICAL_MODE or state.mode.started:
            self.label.text = ''
        else:
            self.label.text = bwaccel.banner()


class LogoUpperLabel:
    """The word "Brain" above the brain logo."""

    def __init__(self) -> None:
        # The program name is not translated.
        self.label = pyglet.text.Label(
            'Brain', font_size=calc_fontsize(11), weight='bold',
            color=state.cfg.COLOR_TEXT, x=state.field.center_x,
            y=state.field.center_y + scale_to_height(30),
            anchor_x='center', anchor_y='center')

    def draw(self) -> None:
        self.label.draw()


class LogoLowerLabel:
    """The word "Workshop" below the brain logo."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            'Workshop', font_size=calc_fontsize(11), weight='bold',
            color=state.cfg.COLOR_TEXT, x=state.field.center_x,
            y=state.field.center_y - scale_to_height(27),
            anchor_x='center', anchor_y='center')

    def draw(self) -> None:
        self.label.draw()


class PausedLabel:
    """The word "Paused" in the middle of the field."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=(64, 64, 255, 255),
            x=state.field.center_x, y=state.field.center_y,
            anchor_x='center', anchor_y='center', batch=state.batch)
        self.update()

    def update(self) -> None:
        self.label.text = 'Paused' if state.mode.paused else ''


class CongratsLabel:
    """End-of-session praise and level-change notice."""

    def __init__(self) -> None:
        self.label = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=(255, 32, 32, 255),
            x=state.field.center_x, y=from_top_edge(47),
            anchor_x='center', anchor_y='center', batch=state.batch)
        self.update()

    def update(self, show: bool = False, advance: bool = False,
               fallback: bool = False, awesome: bool = False,
               great: bool = False, good: bool = False,
               perfect: bool = False) -> None:
        parts: List[str] = []
        if show and not CLINICAL_MODE and state.cfg.USE_SESSION_FEEDBACK:
            if perfect:
                parts.append(_('Perfect score! '))
            elif awesome:
                parts.append(_('Awesome score! '))
            elif great:
                parts.append(_('Great score! '))
            elif good:
                parts.append(_('Not bad! '))
            else:
                parts.append(_("Keep trying. You're getting there! "))
        if advance:
            parts.append(_('N-Back increased'))
        elif fallback:
            parts.append(_('N-Back decreased'))
        self.label.text = ''.join(parts)
