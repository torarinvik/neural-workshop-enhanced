# -*- coding: utf-8 -*-
"""The stepped agent boundary for the carried-through tasks: a state
shown once, then events a frame at a time.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.carried'


class RunningCountEnv(FrameRung):
    """Running Count: Four ports, one a card, left to right. Presses
    before the question is put are ignored."""

    task_class = (UI, 'RunningCount')
    ports = 4


class BeadPileEnv(FrameRung):
    """Bead Pile: Four ports, one a card, top to bottom. Presses before
    the question is put are ignored."""

    task_class = (UI, 'BeadPile')
    ports = 4


class ArrowWalkEnv(FrameRung):
    """Arrow Walk: Four ports, one a square, in reading order. Presses
    before the question is put are ignored."""

    task_class = (UI, 'ArrowWalk')
    ports = 4


class ChevronWalkEnv(FrameRung):
    """Chevron Walk: Four ports, one a square, from the bottom right
    back to the top left. Presses before the question is put are
    ignored."""

    task_class = (UI, 'ChevronWalk')
    ports = 4


ENVS = (RunningCountEnv, BeadPileEnv, ArrowWalkEnv, ChevronWalkEnv)

verify_running_count_outcome = RunningCountEnv.verifier()
verify_bead_pile_outcome = BeadPileEnv.verifier()
verify_arrow_walk_outcome = ArrowWalkEnv.verifier()
verify_chevron_walk_outcome = ChevronWalkEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
