# -*- coding: utf-8 -*-
"""Wait and See.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class WaitAndSeeEnv(FrameRung):
    """Wait and See."""

    task_class = ('neural_workshop.ui.waitandsee', 'WaitAndSee')
    ports = 4


verify_wait_and_see_outcome = WaitAndSeeEnv.verifier()

__all__ = ['WaitAndSeeEnv']
