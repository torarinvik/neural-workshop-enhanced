# -*- coding: utf-8 -*-
"""Standing Order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class StandingOrderEnv(FrameRung):
    """Standing Order."""

    task_class = ('neural_workshop.ui.standingorder', 'StandingOrder')
    ports = 4


verify_standing_order_outcome = StandingOrderEnv.verifier()

__all__ = ['StandingOrderEnv']
