# -*- coding: utf-8 -*-
"""The stepped agent boundary for the hands-off tasks: a cue, a wait
closed to presses, then the question.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.handsoff'


class HandsOffEnv(FrameRung):
    """Hands Off: Four ports, one a square, in reading order. Any press
    before the question is put ends the trial unpaid."""

    task_class = (UI, 'HandsOff')
    ports = 4


class BusyWaitEnv(FrameRung):
    """Busy Wait: Four ports, one a square, in reading order. During
    the wait a dot lights in a square, a new one every two frames, and
    its port must be pressed once while it shows; any other press
    before the question is put, or a dot left unpressed, ends the trial
    unpaid."""

    task_class = (UI, 'BusyWait')
    ports = 4


ENVS = (HandsOffEnv, BusyWaitEnv)

verify_hands_off_outcome = HandsOffEnv.verifier()
verify_busy_wait_outcome = BusyWaitEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
