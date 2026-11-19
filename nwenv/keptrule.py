# -*- coding: utf-8 -*-
"""The stepped agent boundary for the rule that holds across trials.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class SameOrOppositeEnv(FrameRung):
    """Same or Opposite: Four ports, one a square, in reading order. A
    sign on the first trial of a block of n trials says whether to press
    where the square is or across from it, and is not shown again. Any
    press before the question is put ends the trial unpaid."""

    task_class = ('neural_workshop.ui.keptrule', 'SameOrOpposite')
    ports = 4


verify_same_or_opposite_outcome = SameOrOppositeEnv.verifier()

__all__ = ['SameOrOppositeEnv']
