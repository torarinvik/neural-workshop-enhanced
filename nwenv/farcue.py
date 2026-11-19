# -*- coding: utf-8 -*-
"""The stepped agent boundary for the far-cue tasks: a mark, many
look-alike frames, then the question.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.farcue'


class TheMarkedOneEnv(FrameRung):
    """The Marked One: Four ports, one a card, left to right. Presses
    before the question is put are ignored."""

    task_class = (UI, 'TheMarkedOne')
    ports = 4


class FlaggedBeadEnv(FrameRung):
    """Flagged Bead: Four ports, one a card, top to bottom. Presses
    before the question is put are ignored."""

    task_class = (UI, 'FlaggedBead')
    ports = 4


ENVS = (TheMarkedOneEnv, FlaggedBeadEnv)

verify_the_marked_one_outcome = TheMarkedOneEnv.verifier()
verify_flagged_bead_outcome = FlaggedBeadEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
