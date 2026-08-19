# -*- coding: utf-8 -*-
"""Discovery and loading of the sound, music and sprite sets in ``res/``.

Each resource type is a directory of *sets*; a set is a directory of
files. ``resourcepaths['sprites']['pentominoes']`` is the sorted list of
image files in that set. Which extensions count depends on whether
ffmpeg is available, so this must run after the config is loaded.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import pyglet

from . import runtime, state
from .constants import WEB_PYGLET_DOWNLOAD
from .paths import get_res_dir, quit_with_error
from .i18n import _

#: ``{restype: {setname: [path, ...]}}``.
resourcepaths: Dict[str, Dict[str, List[str]]] = {}

#: ``{setname: {basename: Source}}`` for every sound set.
sounds: Dict[str, Dict[str, Any]] = {}

#: Loaded applause sources, empty when applause is disabled.
applause_sounds: List[Any] = []

_SUPPORTED_TYPES: Dict[str, List[str]] = {
    'sounds': ['wav'],
    'music': ['wav', 'ogg', 'mp3', 'aac', 'mp2', 'ac3', 'm4a'],
    'sprites': ['png', 'jpg', 'bmp'],
}

_DEP_WARNING = """Warning: Could not load AVbin. Music disabled.

This is usually due to Windows Data Execution Prevention (DEP). Due to a bug in
AVbin, a library used for decoding sound files, music is not available when \
DEP is enabled. To enable music, disable DEP for Brain Workshop. To simply get \
rid of this message, set USE_MUSIC = False in your config.ini file.

To disable DEP:

1. Open Control Panel -> System
2. Select Advanced System Settings
3. Click on Performance -> Settings
4. Click on the Data Execution Prevention tab
5. Either select the "Turn on DEP for essential Windows programs and services \
only" option, or add an exception for Brain Workshop.

Press any key to continue without music support.
"""


def _test_music() -> None:
    """Decide whether compressed audio can be decoded at all."""
    from .ui.message import Message
    try:
        from pyglet.media import have_ffmpeg
        pyglet.media.have_avbin = have_ffmpeg()
        if not pyglet.media.have_avbin:
            state.cfg.USE_MUSIC = False
    except ImportError as exc:
        runtime.debug_msg(exc)
        state.cfg.USE_MUSIC = False
        pyglet.media.have_avbin = False
        print(_('AVBin not detected. Music disabled.'))
        print(_('Download AVBin from: https://avbin.github.io'))
    except Exception as exc:  # WindowsError
        runtime.debug_msg(exc)
        state.cfg.USE_MUSIC = False
        pyglet.media.have_avbin = False
        Message(_DEP_WARNING)


def _supported_types() -> Dict[str, List[str]]:
    """Extensions to index, given what the media backend can decode."""
    types = {k: list(v) for k, v in _SUPPORTED_TYPES.items()}
    if pyglet.media.have_avbin:
        types['sounds'] = types['music']
    elif state.cfg.USE_MUSIC:
        types['music'] = types['sounds']
    else:
        del types['music']
    types['misc'] = types['sounds'] + types['sprites']
    return types


def _index_resources(res_path: str,
                     types: Dict[str, List[str]]) -> Dict[str, Dict[str, List[str]]]:
    """Walk ``res/`` and collect every non-empty set of each type."""
    found: Dict[str, Dict[str, List[str]]] = {}
    for restype, extensions in types.items():
        sets: Dict[str, List[str]] = {}
        typedir = os.path.join(res_path, restype)
        for folder in os.listdir(typedir):
            folderpath = os.path.join(typedir, folder)
            if not os.path.isdir(folderpath):
                continue
            contents = sorted(os.path.join(folderpath, obj)
                              for obj in os.listdir(folderpath)
                              if obj[-3:] in extensions)
            if contents:
                sets[folder] = contents
        if sets:
            found[restype] = sets
    return found


def initialize() -> None:
    """Index ``res/`` and load every sound into memory."""
    global resourcepaths, sounds, applause_sounds

    res_path = get_res_dir()
    if not os.access(res_path, os.F_OK):
        quit_with_error(
            _('Error: the resource folder\n%s') % res_path
            + _(' does not exist or is not readable.  Exiting'), trace=False)
    if pyglet.version < '2':
        quit_with_error(
            _('Error: pyglet >=2 is required.\n')
            + _('You probably have an older version of pyglet installed.\n')
            + _('Please visit %s') % WEB_PYGLET_DOWNLOAD, trace=False)

    _test_music()
    resourcepaths = _index_resources(res_path, _supported_types())

    sounds = {}
    for setname, paths in resourcepaths['sounds'].items():
        sounds[setname] = {
            os.path.basename(path).split('.')[0]:
                pyglet.media.load(path, streaming=False)
            for path in paths
        }

    applause_sounds = []
    if state.cfg.USE_APPLAUSE:
        applause_sounds = [pyglet.media.load(path, streaming=False)
                           for path in resourcepaths['misc']['applause']]
