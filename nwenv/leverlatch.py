# -*- coding: utf-8 -*-
"""Lever and Latch.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .longwalk import _Rung


class LeverAndLatchEnv(_Rung):
    """Lever and Latch."""

    task_class = ('neural_workshop.ui.leverlatch', 'LeverAndLatch')
    ports = 4


verify_lever_and_latch_outcome = LeverAndLatchEnv.verifier()

__all__ = ['LeverAndLatchEnv']
