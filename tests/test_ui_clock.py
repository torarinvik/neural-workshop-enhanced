#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Every deadline a task reads belongs to whoever is driving it.

A task that gates on ``time.time()`` cannot be driven a step at a time.
The agent boundary advances a virtual clock — one tick per published
frame, at a rate the caller chose — so a task reading the wall instead
either never advances at all (a feedback window that waits 1.6 real
seconds, in a driver that steps as fast as it can draw) or advances at
a rate set by how quick the machine is, which is the same run being a
different experiment on different hardware.

The convention is one line in ``__init__``::

    #: Swapped out by an agent environment for a virtual clock.
    self.clock = time.time

and every deadline through ``self.clock()``. :meth:`TaskEnv.reset`
replaces it, and everything downstream — exposure windows, feedback
windows, reaction times, elapsed-time scores — becomes the driver's.

Fifteen of the twenty-three task screens read the wall directly and
every one of them was undriveable because of it. The scan below is what
survives us: it fails the build the next time a task reaches for
``time.time()``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import ast
import os
import unittest

from uisupport import ROOT

#: Where the task screens live. Only these are driven by the boundary;
#: the rest of the programme may read the wall clock as it likes.
TASK_DIR = os.path.join(ROOT, 'neural_workshop', 'ui')

#: Files under it that are not tasks. Menus, chrome and helpers are
#: never stepped, so their deadlines are nobody's but the player's.
NOT_TASKS = frozenset({
    '__init__.py', 'cursor.py', 'effects.py', 'field.py', 'gameselect.py',
    'graph.py', 'hud.py', 'menu.py', 'message.py', 'readouts.py',
    'screens.py', 'taskhub.py', 'taskoptions.py', 'textinput.py',
    'trialui.py', 'verdict.py',
})

#: The one place ``time.time`` may be named: installing the default.
INSTALLING = 'self.clock = time.time'


def task_files():
    for name in sorted(os.listdir(TASK_DIR)):
        if name.endswith('.py') and name not in NOT_TASKS:
            yield name


def wall_clock_reads(path):
    """Lines calling ``time.time()`` other than to install the default."""
    with open(path, encoding='utf-8') as handle:
        source = handle.read()
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == 'time'
                and isinstance(func.value, ast.Name)
                and func.value.id == 'time'):
            found.append(node.lineno)
    lines = source.splitlines()
    return [number for number in found
            if INSTALLING not in lines[number - 1]]


class NoTaskReadsTheWallClock(unittest.TestCase):
    """The rule, and a guard on the rule."""

    def test_the_scan_sees_the_tasks(self):
        names = list(task_files())
        self.assertIn('sokoban.py', names)
        self.assertIn('pursuit.py', names)
        self.assertGreater(len(names), 20)

    def test_no_task_calls_time_time(self):
        offenders = []
        for name in task_files():
            for number in wall_clock_reads(os.path.join(TASK_DIR, name)):
                offenders.append('neural_workshop/ui/%s:%d' % (name, number))
        self.assertEqual(offenders, [], '\n'.join(
            ['these read the wall clock instead of self.clock(), which '
             'makes them undriveable a step at a time:'] + offenders))

    def test_every_task_installs_a_clock(self):
        missing = []
        for name in task_files():
            with open(os.path.join(TASK_DIR, name), encoding='utf-8') as f:
                if INSTALLING not in f.read():
                    missing.append(name)
        self.assertEqual(missing, [], 'these have no swappable clock: %s'
                                      % missing)

    def test_the_scan_would_catch_a_new_offender(self):
        """Guard the guard: a rule that cannot fail is not a rule."""
        import tempfile
        sample = ('import time\n'
                  'class T:\n'
                  '    def __init__(self):\n'
                  '        self.clock = time.time\n'
                  '    def go(self):\n'
                  '        self.until = time.time() + 1\n')
        handle = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False)
        try:
            handle.write(sample)
            handle.close()
            self.assertEqual(wall_clock_reads(handle.name), [6])
        finally:
            os.unlink(handle.name)

    def test_the_scan_leaves_the_installing_line_alone(self):
        import tempfile
        sample = ('import time\n'
                  'class T:\n'
                  '    def __init__(self):\n'
                  '        self.clock = time.time\n')
        handle = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False)
        try:
            handle.write(sample)
            handle.close()
            self.assertEqual(wall_clock_reads(handle.name), [])
        finally:
            os.unlink(handle.name)


if __name__ == '__main__':
    unittest.main()
