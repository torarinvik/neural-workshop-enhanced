# -*- coding: utf-8 -*-
"""Neural Workshop: a Dual N-Back gym in Python.

A fork of Brain Workshop, whose original is at http://brainworkshop.net/.

The package is layered so that each file can be read on its own:

``constants`` / ``runtime`` / ``paths``
    Process-level facts: what never changes, what the command line
    changed, and where things live on disk.
``config`` / ``configdefaults``
    Reading and normalising ``config.ini``.
``state``
    The live singletons. Every module reaches them through this module
    rather than importing them by value, because some are rebound.
``geometry`` / ``timing`` / ``grid``
    Pure helpers over the window, the clock and the board.
``gamemode`` / ``matching`` / ``stats`` / ``session``
    The game itself: what a mode is, what counts as a match, what is
    recorded, and how a session runs.
``ui``
    Everything drawn on screen.
``events`` / ``bootstrap``
    Input handling and the phase machine; then the assembly order that
    turns all of the above into a running program.

Importing this package installs gettext, so ``_()`` is available as a
builtin to every module in it.

Copyright (C) 2009-2011: Paul Hoskinson (plhosk@gmail.com)
Copyright (C) 2017-2018: Samantha McVey (samantham@posteo.net)
SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import gettext
import os
import sys

import pyglet

from .constants import VERSION
from .runtime import wants_headless

__version__ = VERSION

# Translations must be installed before any module builds a label.
gettext.install('messages', localedir=os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'res', 'i18n'))

if wants_headless():
    # pyglet's own headless backend needs EGL/OSMesa, which is Linux only.
    # Elsewhere we keep a native window and hide it, so GL readback works.
    # Silent audio has to be selected before pyglet.media starts OpenAL.
    pyglet.options['audio'] = ('silent',)
    if sys.platform.startswith('linux'):
        try:
            pyglet.options['headless'] = True
        except Exception:
            pass

__all__ = ['VERSION', '__version__']
