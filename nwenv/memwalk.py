# -*- coding: utf-8 -*-
"""The stepped agent boundary for the walks from memory: where to go
shows for two frames and is hidden, then the walk.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`):
the goals show for two steps at two steps a second.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.memwalk'


class GoneFromViewEnv(FrameRung):
    """Gone From View: Four ports: up, down, left, right. Presses while
    the goal shows are ignored. Green means the goal was reached within
    the steps allowed."""

    task_class = (UI, 'GoneFromView')
    ports = 4


class InThatOrderEnv(FrameRung):
    """In That Order: Four ports: up, down, left, right. Presses while
    the places show are ignored. Green means both were visited, in the
    order shown, within the steps allowed."""

    task_class = (UI, 'InThatOrder')
    ports = 4


verify_gone_from_view_outcome = GoneFromViewEnv.verifier()
verify_in_that_order_outcome = InThatOrderEnv.verifier()

__all__ = ['GoneFromViewEnv', 'InThatOrderEnv']
