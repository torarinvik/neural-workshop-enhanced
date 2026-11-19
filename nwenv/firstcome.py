# -*- coding: utf-8 -*-
"""First Come.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class FirstComeEnv(FrameRung):
    """First Come."""

    task_class = ('neural_workshop.ui.firstcome', 'FirstCome')
    ports = 4


verify_first_come_outcome = FirstComeEnv.verifier()

__all__ = ['FirstComeEnv']
