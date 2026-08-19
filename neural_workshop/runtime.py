# -*- coding: utf-8 -*-
"""Process-level flags and the small helpers that read them.

These values are decided from ``sys.argv`` and the environment at start-up
and a few of them change later (``USER`` and friends when the player
switches profiles). Always reach them through the module —
``runtime.USER``, never ``from .runtime import USER`` — so that a rebind
here is visible to every other module.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys
from typing import Optional

#: Verbose tracing (``--debug``).
DEBUG: bool = False

#: Wait for vertical retrace. Off by default: it caps agent throughput.
VSYNC: bool = False

#: No visible window; audio is captured rather than played.
HEADLESS: bool = False

#: Config file for the active user, relative to the data directory.
CONFIGFILE: str = 'config.ini'

#: Tamper-resistant clinical log for the active user.
STATS_BINARY: str = 'logfile.dat'

#: The active player profile.
USER: str = 'default'

#: Seconds per tick, kept in sync with ``cfg.TICK_DURATION_MS``.
TICK_DURATION: float = 0.1


def env_flag(name: str, default: str = '') -> bool:
    """True if environment variable *name* is set to a truthy word."""
    return os.environ.get(name, default).lower() in ('1', 'true', 'yes', 'on')


def wants_headless() -> bool:
    """Whether this process was asked to run without a visible window.

    Called before :mod:`pyglet` is configured, so it must not touch any
    other module in the package.
    """
    return '--headless' in sys.argv or env_flag('NW_HEADLESS')


def get_argv(arg: str) -> Optional[str]:
    """Return the value following command-line flag *arg*, if present."""
    if arg not in sys.argv:
        return None
    index = sys.argv.index(arg)
    if index + 1 < len(sys.argv):
        return sys.argv[index + 1]
    error_msg('Expected an argument following %s' % arg)
    raise SystemExit(1)


def debug_msg(msg: object) -> None:
    """Print *msg* when ``--debug`` is on; exceptions get a line number."""
    if not DEBUG:
        return
    if isinstance(msg, Exception):
        _exc_type, _exc_obj, exc_tb = sys.exc_info()
        line = exc_tb.tb_lineno if exc_tb is not None else -1
        print('debug: %s Line %i' % (msg, line))
    else:
        print('debug: %s' % (msg,))


def error_msg(msg: str, e: Optional[BaseException] = None) -> None:
    """Report an error, with the raising line number under ``--debug``."""
    if DEBUG and e:
        _exc_type, _exc_obj, exc_tb = sys.exc_info()
        line = exc_tb.tb_lineno if exc_tb is not None else -1
        print('ERROR: %s\n\t%s Line %i' % (msg, e, line))
    else:
        print('ERROR: %s' % (msg,))


def apply_command_line_flags() -> None:
    """Latch ``--debug`` / ``--headless`` / ``--vsync`` / ``--configfile``."""
    global DEBUG, HEADLESS, VSYNC, CONFIGFILE
    if '--debug' in sys.argv:
        DEBUG = True
    if wants_headless():
        HEADLESS = True
    # Vsync caps throughput; leave it off in headless agent runs.
    if '--vsync' in sys.argv or (sys.platform == 'darwin' and not HEADLESS):
        VSYNC = True
    configfile = get_argv('--configfile')
    if configfile:
        CONFIGFILE = configfile


def set_user_files(user: str) -> None:
    """Point ``USER``/``CONFIGFILE``/``STATS_BINARY`` at profile *user*."""
    global USER, CONFIGFILE, STATS_BINARY
    USER = user
    if user.lower() == 'default':
        CONFIGFILE = 'config.ini'
        STATS_BINARY = 'logfile.dat'
    else:
        CONFIGFILE = user + '-config.ini'
        STATS_BINARY = user + '-logfile.dat'
