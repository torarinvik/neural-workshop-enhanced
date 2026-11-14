#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Runner for the whole user-interface suite.

The tests themselves live in ``test_ui_menus``, ``test_ui_screens``,
``test_ui_tasks``, ``test_ui_display``, ``test_ui_longterm``,
``test_ui_matrices``, ``test_ui_reasoning``, ``test_ui_jigsaw``,
``test_tetris``, ``test_ninarow``, ``test_trivia`` and ``test_ui_units``;
this module gathers them so
that ``python tests/test_ui_smoke.py`` still runs everything.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    # Keep this compatibility runner explicit.  Importing these modules at
    # collection time made pytest run the entire UI suite a second time.
    from test_ui_attention import *   # noqa: F401,F403,E402
    from test_ui_display import *     # noqa: F401,F403,E402
    from test_ui_jigsaw import *      # noqa: F401,F403,E402
    from test_ui_videopuzzle import *  # noqa: F401,F403,E402
    from test_camera import *          # noqa: F401,F403,E402
    from test_ui_longterm import *    # noqa: F401,F403,E402
    from test_ui_matrices import *    # noqa: F401,F403,E402
    from test_ui_menus import *       # noqa: F401,F403,E402
    from test_ui_perception import *  # noqa: F401,F403,E402
    from test_sokoban import *        # noqa: F401,F403,E402
    from test_tetris import *         # noqa: F401,F403,E402
    from test_ninarow import *        # noqa: F401,F403,E402
    from test_trivia import *         # noqa: F401,F403,E402
    from test_ui_planning import *    # noqa: F401,F403,E402
    from test_ui_reasoning import *   # noqa: F401,F403,E402
    from test_ui_screens import *     # noqa: F401,F403,E402
    from test_ui_tasks import *       # noqa: F401,F403,E402
    from test_ui_units import *       # noqa: F401,F403,E402

    unittest.main(verbosity=2)
