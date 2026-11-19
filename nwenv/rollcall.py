# -*- coding: utf-8 -*-
"""Roll Call.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class RollCallEnv(FrameRung):
    """Roll Call."""

    task_class = ('neural_workshop.ui.rollcall', 'RollCall')
    ports = 4


verify_roll_call_outcome = RollCallEnv.verifier()

__all__ = ['RollCallEnv']
