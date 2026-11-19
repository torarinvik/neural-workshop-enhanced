# -*- coding: utf-8 -*-
"""Arrow Walk.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class ArrowWalkEnv(FrameRung):
    """Arrow Walk."""

    task_class = ('neural_workshop.ui.arrowwalk', 'ArrowWalk')
    ports = 4


verify_arrow_walk_outcome = ArrowWalkEnv.verifier()

__all__ = ['ArrowWalkEnv']
