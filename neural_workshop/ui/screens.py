# -*- coding: utf-8 -*-
"""The concrete menu screens: user, language, options, images and sounds.

The game-mode screen is large enough to live on its own, in
:mod:`neural_workshop.ui.gameselect`.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
from typing import Dict, List

from .. import state
from ..paths import get_res_dir
from .menu import BLANK_LINE, Cycler, Menu
from ..i18n import _


class UserScreen(Menu):
    """Pick an existing profile or create a new one."""

    def __init__(self) -> None:
        from .. import runtime
        from ..session import get_users
        self.users: List[str] = [_('New user'), BLANK_LINE] + get_users()
        Menu.__init__(self, options=self.users,
                      title=_('Please select your user profile'),
                      choose_once=True,
                      default=self.users.index(runtime.USER))

    def save(self) -> None:
        self.select()  # Enter should choose a user too
        Menu.save(self)

    def choose(self, k: str, i: int) -> None:
        from .. import runtime
        from ..session import set_user
        from .textinput import TextInputScreen
        newuser = self.users[i]
        if newuser == _('New user'):
            TextInputScreen(_('Enter new user name:'), runtime.USER,
                            callback=set_user)
        else:
            set_user(newuser)


class LanguageScreen(Menu):
    """Pick one of the compiled translations in ``res/i18n``."""

    def __init__(self) -> None:
        i18n_dir = os.path.join(get_res_dir(), 'i18n')
        self.languages = sorted(
            fn for fn in os.listdir(i18n_dir) if fn.lower().endswith('.mo'))
        try:
            default = self.languages.index('%s.mo' % state.cfg.LANGUAGE)
        except (TypeError, ValueError):
            default = 0  # LANGUAGE unset or not installed
        Menu.__init__(self, options=self.languages,
                      title=_('Please select your preferred language'),
                      choose_once=True, default=default)

    def save(self) -> None:
        self.select()
        Menu.save(self)

    def choose(self, k: str, i: int) -> None:
        # Switching language at runtime is not implemented yet; the
        # selection is remembered only for the next launch.
        state.cfg.LANGUAGE = self.languages[i].rsplit('.', 1)[0]


class OptionsScreen(Menu):
    """Raw view of every config key. Rough, but occasionally useful."""

    def __init__(self) -> None:
        Menu.__init__(self, options=sorted(state.cfg), values=state.cfg,
                      title=_('Configuration'))


class ImageSelect(Menu):
    """Choose which sprite sets the image n-back draws from."""

    def __init__(self) -> None:
        from .. import resources
        self.new_sets: Dict[str, bool] = {
            name: name in state.cfg.IMAGE_SETS
            for name in resources.resourcepaths['sprites']}
        Menu.__init__(
            self, sorted(self.new_sets), self.new_sets,
            title=_('Choose images to use for the Image n-back tasks.'))

    def close(self) -> None:
        from ..session import update_all_labels
        state.cfg.IMAGE_SETS[:] = [k for k, v in self.new_sets.items() if v]
        Menu.close(self)
        update_all_labels()

    def select(self, steps: int = 1) -> None:
        Menu.select(self, steps)
        # At least one set must stay enabled.
        if not [v for v in self.values.values()
                if v and not isinstance(v, Cycler)]:
            i = 0
            if self.selpos == 0:
                i = random.randint(1, len(self.options) - 1)
            self.values[self.options[i]] = True
            self.update_labels()


class SoundSelect(Menu):
    """Choose the sound sets and stereo channel for each audio stream."""

    #: Sound set reserved for arithmetic mode, never player-selectable.
    RESERVED_SET = 'operations'

    def __init__(self) -> None:
        from .. import resources
        audiosets = [name for name in resources.resourcepaths['sounds']
                     if name != self.RESERVED_SET]
        self.new_sets: Dict[str, bool] = {}
        for audio in audiosets:
            self.new_sets['1' + audio] = audio in state.cfg.AUDIO1_SETS
            self.new_sets['2' + audio] = audio in state.cfg.AUDIO2_SETS

        options = sorted(self.new_sets)
        # A blank row between the two channels, and before the channel picker.
        options.insert(len(self.new_sets) // 2, BLANK_LINE)
        options.append(BLANK_LINE)
        options.extend(['cfg.CHANNEL_AUDIO1', 'cfg.CHANNEL_AUDIO2'])

        lcr = ['left', 'right', 'center']
        values: Dict[str, object] = dict(self.new_sets)
        values['cfg.CHANNEL_AUDIO1'] = Cycler(
            lcr, default=lcr.index(state.cfg.CHANNEL_AUDIO1))
        values['cfg.CHANNEL_AUDIO2'] = Cycler(
            lcr, default=lcr.index(state.cfg.CHANNEL_AUDIO2))

        names: Dict[str, str] = {}
        for op in options:
            if op.startswith('1') or op.startswith('2'):
                names[op] = _("Use sound set '%s' for channel %s") % (op[1:],
                                                                     op[0])
            elif 'CHANNEL_AUDIO' in op:
                names[op] = 'Channel %i is' % (2 if op[-1] == '2' else 1)
        Menu.__init__(self, options, values, {}, names,
                      title=_('Choose sound sets to Sound n-back tasks.'))

    def close(self) -> None:
        from ..session import update_all_labels
        state.cfg.AUDIO1_SETS = [k[1:] for k, v in self.new_sets.items()
                                 if k.startswith('1') and v]
        state.cfg.AUDIO2_SETS = [k[1:] for k, v in self.new_sets.items()
                                 if k.startswith('2') and v]
        state.cfg.CHANNEL_AUDIO1 = self.values['cfg.CHANNEL_AUDIO1'].value()
        state.cfg.CHANNEL_AUDIO2 = self.values['cfg.CHANNEL_AUDIO2'].value()
        Menu.close(self)
        update_all_labels()

    def select(self, steps: int = 1) -> None:
        Menu.select(self, steps)
        from .. import resources
        # Each channel must keep at least one sound set.
        for channel in ('1', '2'):
            if [v for k, v in self.values.items()
                    if k.startswith(channel) and v and not isinstance(v, Cycler)]:
                continue
            count = len([name for name in resources.resourcepaths['sounds']
                         if name != self.RESERVED_SET])
            i = 0
            if self.selpos == 0:
                i = random.randint(1, count - 1)
            elif self.selpos == count + 1:
                i = random.randint(count + 2, 2 * count)
            elif self.selpos > count + 1:
                i = count + 1
            self.values[self.options[i]] = True
        self.update_labels()
