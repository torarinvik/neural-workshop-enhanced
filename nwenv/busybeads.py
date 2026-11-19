# -*- coding: utf-8 -*-
"""Busy Beads.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class BusyBeadsEnv(FrameRung):
    """Busy Beads."""

    task_class = ('neural_workshop.ui.busybeads', 'BusyBeads')
    ports = 4


verify_busy_beads_outcome = BusyBeadsEnv.verifier()

__all__ = ['BusyBeadsEnv']
