# -*- coding: utf-8 -*-
"""The stepped agent boundary for the wait of uneven length.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class UnevenWaitEnv(FrameRung):
    """Uneven Wait: Four ports, one a square, in reading order. The
    wait is drawn anew each trial, from n to 3n frames at rung n. Any
    press before the question is put ends the trial unpaid."""

    task_class = ('neural_workshop.ui.unevenwait', 'UnevenWait')
    ports = 4


verify_uneven_wait_outcome = UnevenWaitEnv.verifier()

__all__ = ['UnevenWaitEnv']
