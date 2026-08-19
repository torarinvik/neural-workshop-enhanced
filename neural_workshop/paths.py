# -*- coding: utf-8 -*-
"""Where the game keeps its resources, config and per-user data.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from typing import NoReturn, Optional

import pyglet

from . import runtime
from .constants import FOLDER_DATA, FOLDER_RES
from .i18n import _


def main_is_frozen() -> bool:
    """True when running from a py2exe/PyInstaller bundle."""
    return hasattr(sys, 'frozen')


def get_main_dir() -> str:
    """Directory of the installed game.

    Resolved against this file rather than ``sys.path[0]``, which is
    wrong under ``python -m unittest discover -s tests``.
    """
    if main_is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_settings_path(name: str) -> str:
    """Per-platform directory for user preferences.

    Copied from ``pyglet.resource`` so we do not have to import that
    module, which recursively indexes the working directory on load.
    """
    if sys.platform in ('cygwin', 'win32'):
        if 'APPDATA' in os.environ:
            return os.path.join(os.environ['APPDATA'], name)
        return os.path.expanduser('~/%s' % name)
    if sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/%s' % name)
    # On *nix we want it lowercase and without spaces: ~/.brainworkshop/data
    return os.path.expanduser('~/.%s' % (name.lower().replace(' ', '')))


def get_data_dir() -> str:
    """Directory holding config, stats and save files."""
    override = runtime.get_argv('--datadir')
    if override:
        return override
    return os.path.join(get_settings_path('Brain Workshop'), FOLDER_DATA)


def get_res_dir() -> str:
    """Directory holding images, sounds and translations."""
    override = runtime.get_argv('--resdir')
    if override:
        return override
    return os.path.join(get_main_dir(), FOLDER_RES)


def ensure_data_dir() -> str:
    """Create the data directory if needed and return it."""
    path = get_data_dir()
    os.makedirs(path, exist_ok=True)
    return path


def load_pyglet_image(path: str) -> pyglet.image.AbstractImage:
    """Load an image and close the file handle (avoids ResourceWarning)."""
    with open(path, 'rb') as handle:
        return pyglet.image.load(filename=path, file=handle)


def dump_pyglet_info() -> NoReturn:
    """Write ``pyglet.info`` output to ``dump.txt`` and exit (``--dump``)."""
    from pyglet import info
    old_stdout = sys.stdout
    dump_path = os.path.join(get_data_dir(), 'dump.txt')
    with open(dump_path, 'w') as handle:
        sys.stdout = handle
        try:
            info.dump()
        finally:
            sys.stdout = old_stdout
    print('pyglet info dumped to %s' % dump_path)
    raise SystemExit(0)


def edit_config_ini() -> NoReturn:
    """Close the window and open the active config file in an editor."""
    from . import state
    if sys.platform == 'win32':
        cmd = 'notepad'
    elif sys.platform == 'darwin':
        cmd = 'open'
    else:
        cmd = 'xdg-open'
    target = os.path.join(get_data_dir(), runtime.CONFIGFILE)
    print('%s "%s"' % (cmd, target))
    if state.window is not None:
        state.window.on_close()
    subprocess.call('%s "%s"' % (cmd, target), shell=True)
    raise SystemExit(0)


def quit_with_error(message: str = '', postmessage: str = '',
                    quit: bool = True, trace: bool = True) -> Optional[NoReturn]:
    """Report a fatal error to stderr and (by default) exit."""
    if message:
        sys.stderr.write(message + '\n')
    if trace:
        sys.stderr.write(_('Full text of error:\n'))
        traceback.print_exc()
    if postmessage:
        sys.stderr.write('\n\n' + postmessage)
    if quit:
        raise SystemExit(1)
    return None
