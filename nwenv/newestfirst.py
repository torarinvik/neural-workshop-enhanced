# -*- coding: utf-8 -*-
"""The stepped agent boundary for the newest counts and the first
counts.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.newestfirst'


class TheNewestCountsEnv(FrameRung):
    """The Newest Counts: Four ports, one a square, in reading order.
    Press the square that lit last. Any press before the question is
    put ends the trial unpaid."""

    task_class = (UI, 'TheNewestCounts')
    ports = 4


class TheFirstCountsEnv(FrameRung):
    """The First Counts: Four ports, one a square, in reading order.
    Press the square that lit first; later ones are decoys. Any press
    before the question is put ends the trial unpaid."""

    task_class = (UI, 'TheFirstCounts')
    ports = 4


ENVS = (TheNewestCountsEnv, TheFirstCountsEnv)

verify_newest_counts_outcome = TheNewestCountsEnv.verifier()
verify_first_counts_outcome = TheFirstCountsEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
