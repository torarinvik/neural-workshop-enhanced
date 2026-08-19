#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Runner for the whole agent-boundary suite.

The tests themselves live in ``test_env_frames``, ``test_env_receipts``,
``test_env_parity`` and ``test_env_modes``; this module gathers them so
that ``python tests/test_nwenv.py`` still runs everything.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_env_frames import *      # noqa: F401,F403,E402
from test_env_modes import *       # noqa: F401,F403,E402
from test_env_parity import *      # noqa: F401,F403,E402
from test_env_receipts import *    # noqa: F401,F403,E402

if __name__ == '__main__':
    unittest.main(verbosity=2)
