# -*- coding: utf-8 -*-
"""The stepped agent boundary for several cues kept, one asked for.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class WhichWasWhereEnv(FrameRung):
    """Which Was Where?: Four ports, one a square, in reading order. Two
    to four squares light, each in its own colour; the question shows
    one of the colours. Any press before the question is put ends the
    trial unpaid."""

    task_class = ('neural_workshop.ui.severalcues', 'WhichWasWhere')
    ports = 4


verify_which_was_where_outcome = WhichWasWhereEnv.verifier()

__all__ = ['WhichWasWhereEnv']
