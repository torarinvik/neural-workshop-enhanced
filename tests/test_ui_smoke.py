#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Runner for the whole user-interface suite.

The tests themselves live in ``test_ui_menus``, ``test_ui_screens``,
``test_ui_tasks``, ``test_ui_display`` and ``test_ui_units``; this module gathers them so
that ``python tests/test_ui_smoke.py`` still runs everything.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_ui_display import *     # noqa: F401,F403,E402
from test_ui_menus import *       # noqa: F401,F403,E402
from test_ui_screens import *     # noqa: F401,F403,E402
from test_ui_tasks import *       # noqa: F401,F403,E402
from test_ui_units import *       # noqa: F401,F403,E402

if __name__ == '__main__':
    unittest.main(verbosity=2)
