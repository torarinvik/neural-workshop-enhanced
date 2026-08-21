# -*- coding: utf-8 -*-
"""Shared setup for the agent-boundary tests.

Importing this module configures the environment for a fast headless
run and imports the game, which is a side effect the tests depend on.
``ENV_IMPORT_ERROR`` is not None when no GL context could be created,
and every test module skips itself in that case.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import sys
import unittest
import warnings
from typing import Any, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ['NW_HEADLESS'] = '1'
os.environ['NW_TICK_MS'] = '1'
os.environ['NW_TRIAL_MS'] = '10'
os.environ['NW_STIM_MS'] = '500'

warnings.filterwarnings('ignore', category=ResourceWarning)

try:
    import bwaccel
    import brainworkshop as bw
    from nwenv import (DiagnosticEnv, MonkeyLadderEnv, NeuralWorkshopEnv,
                       OutOfSightEnv, derive_ladder_outcome,
                       derive_public_outcome, derive_sight_outcome,
                       diagnose_public_outcome, digest_rgba,
                       render_significant_frame, verify_ladder_outcome,
                       verify_public_outcome, verify_public_pixels,
                       verify_sight_outcome)
    ENV_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - no GL context available
    bwaccel = None
    bw = None
    DiagnosticEnv = None
    NeuralWorkshopEnv = None
    MonkeyLadderEnv = None
    OutOfSightEnv = None
    derive_ladder_outcome = None
    verify_ladder_outcome = None
    derive_public_outcome = None
    derive_sight_outcome = None
    verify_sight_outcome = None
    diagnose_public_outcome = None
    digest_rgba = None
    render_significant_frame = None
    verify_public_outcome = None
    verify_public_pixels = None
    ENV_IMPORT_ERROR = exc

# Imported on its own rather than folded into the tuple above, so that
# adding the fog boundary edits no line another agent may be holding.
try:
    from nwenv import (FogOfWarEnv, derive_fog_outcome, make_fog_env,
                       verify_fog_outcome)
except Exception:  # pragma: no cover - no GL context available
    FogOfWarEnv = None
    derive_fog_outcome = None
    make_fog_env = None
    verify_fog_outcome = None


#: Decorator every test class in this suite carries.
requires_env = unittest.skipIf(
    DiagnosticEnv is None, 'nwenv import failed: %s' % ENV_IMPORT_ERROR)


def ports_for(kind: str) -> List[int]:
    """Ports whose match verdict is *kind* ('correct' or 'incorrect').

    Uses privileged state that a learner never sees; tests only.
    """
    out = []
    for i, name in enumerate(bw.action_button_names()):
        if bw.check_match(name) == kind:
            out.append(i)
    return out


def advance_to(env: Any, phase: str, limit: int = 40) -> bool:
    """Step *env* until it reaches *phase*, or the session ends."""
    for _ in range(limit):
        if env.probe.phase() == phase:
            return True
        if env.probe.session_done():
            return False
        env.advance()
    return env.probe.phase() == phase


def next_scorable_stimulus(env: Any, limit: int = 40) -> bool:
    """Step to the next stimulus that is far enough in to be scorable."""
    for _ in range(limit):
        if env.probe.session_done():
            return False
        if (env.probe.phase() == 'stimulus'
                and bw.mode.trial_number > bw.mode.back):
            return True
        env.advance()
    return False
