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
    from test_ui_videosequence import *  # noqa: F401,F403,E402
    from test_ui_videojigsaw import *  # noqa: F401,F403,E402
    from test_camera import *          # noqa: F401,F403,E402
    from test_sonar import *           # noqa: F401,F403,E402
    from test_hiddenrule import *      # noqa: F401,F403,E402
    from test_gamble import *  # noqa: F401,F403,E402
    from test_proofreader import *  # noqa: F401,F403,E402
    from test_cipherabyss import *  # noqa: F401,F403,E402
    from test_crazycog import *  # noqa: F401,F403,E402
    from test_nightwatch import *  # noqa: F401,F403,E402
    from test_shadowpuppets import *  # noqa: F401,F403,E402
    from test_semaphore import *  # noqa: F401,F403,E402
    from test_airhockey import *  # noqa: F401,F403,E402
    from test_lockpick import *  # noqa: F401,F403,E402
    from test_bartender import *  # noqa: F401,F403,E402
    from test_signpainter import *  # noqa: F401,F403,E402
    from test_tightrope import *  # noqa: F401,F403,E402
    from test_conductor import *  # noqa: F401,F403,E402
    from test_potter import *  # noqa: F401,F403,E402
    from test_gunslinger import *  # noqa: F401,F403,E402
    from test_loadingdock import *  # noqa: F401,F403,E402
    from test_stagehand import *  # noqa: F401,F403,E402
    from test_safecracker import *  # noqa: F401,F403,E402
    from test_fieldmanual import *  # noqa: F401,F403,E402
    from test_dronehoops import *  # noqa: F401,F403,E402
    from test_captcha import *  # noqa: F401,F403,E402
    from test_echocave import *  # noqa: F401,F403,E402
    from test_catch import *  # noqa: F401,F403,E402
    from test_shadowplay import *  # noqa: F401,F403,E402
    from test_tuner import *  # noqa: F401,F403,E402
    from test_glider import *  # noqa: F401,F403,E402
    from test_holdit import *  # noqa: F401,F403,E402
    from test_timeit import *  # noqa: F401,F403,E402
    from test_beat import *  # noqa: F401,F403,E402
    from test_crossings import *  # noqa: F401,F403,E402
    from test_touching import *  # noqa: F401,F403,E402
    from test_inside import *  # noqa: F401,F403,E402
    from test_drshape import *  # noqa: F401,F403,E402
    from test_damkeeper import *  # noqa: F401,F403,E402
    from test_crossroads import *  # noqa: F401,F403,E402
    from test_balance import *  # noqa: F401,F403,E402
    from test_juggler import *  # noqa: F401,F403,E402
    from test_ferry import *  # noqa: F401,F403,E402
    from test_crane import *  # noqa: F401,F403,E402
    from test_kitchen import *  # noqa: F401,F403,E402
    from test_sokobanlive import *  # noqa: F401,F403,E402
    from test_escort import *  # noqa: F401,F403,E402
    from test_firebreak import *  # noqa: F401,F403,E402
    from test_airtraffic import *  # noqa: F401,F403,E402
    from test_railyard import *  # noqa: F401,F403,E402
    from test_sheet import *  # noqa: F401,F403,E402
    from test_lander import *  # noqa: F401,F403,E402
    from test_bandit import *  # noqa: F401,F403,E402
    from test_delay import *  # noqa: F401,F403,E402
    from test_stopswitch import *  # noqa: F401,F403,E402
    from test_rooms import *  # noqa: F401,F403,E402
    from test_beliefs import *  # noqa: F401,F403,E402
    from test_pov import *  # noqa: F401,F403,E402
    from test_fold import *  # noqa: F401,F403,E402
    from test_sfm import *  # noqa: F401,F403,E402
    from test_nearer import *  # noqa: F401,F403,E402
    from test_mirror import *  # noqa: F401,F403,E402
    from test_errands import *  # noqa: F401,F403,E402
    from test_signals import *  # noqa: F401,F403,E402
    from test_falls import *  # noqa: F401,F403,E402
    from test_browser import *  # noqa: F401,F403,E402
    from test_notebook import *  # noqa: F401,F403,E402
    from test_manual import *  # noqa: F401,F403,E402
    from test_whatnext import *  # noqa: F401,F403,E402
    from test_triage import *  # noqa: F401,F403,E402
    from test_wiring import *  # noqa: F401,F403,E402
    from test_forms import *  # noqa: F401,F403,E402
    from test_bluff import *  # noqa: F401,F403,E402
    from test_dispatch import *        # noqa: F401,F403,E402
    from test_desktop import *         # noqa: F401,F403,E402
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
