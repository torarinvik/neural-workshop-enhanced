# -*- coding: utf-8 -*-
"""Marker Walk.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .ministeps import _Rung


class MarkerWalkEnv(_Rung):
    """Marker Walk."""

    task_class = ('neural_workshop.ui.markerwalk', 'MarkerWalk')
    ports = 4


verify_marker_walk_outcome = MarkerWalkEnv.verifier()

__all__ = ['MarkerWalkEnv']
