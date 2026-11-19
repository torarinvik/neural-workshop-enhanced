# -*- coding: utf-8 -*-
"""Round Again.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung


class RoundAgainEnv(FrameRung):
    """Round Again."""

    task_class = ('neural_workshop.ui.roundagain', 'RoundAgain')
    ports = 4


verify_round_again_outcome = RoundAgainEnv.verifier()

__all__ = ['RoundAgainEnv']
