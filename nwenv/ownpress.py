# -*- coding: utf-8 -*-
"""The stepped agent boundary for the own-presses tasks: the right port
depends on the agent's own earlier presses and payments, which nothing
on screen shows.

Clocked, and safe to step a frame at a time (see :mod:`nwenv.framed`).
A trial with no press counts, for later trials, as one with no press.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import FrameRung

UI = 'neural_workshop.ui.ownpress'


class NextInTurnEnv(FrameRung):
    """Next in Turn: Four ports, one a panel, in reading order. Presses
    before the question is put are ignored."""

    task_class = (UI, 'NextInTurn')
    ports = 4


class RoundAgainEnv(FrameRung):
    """Round Again: Four ports, one a panel, the other way round from
    reading order. Presses before the question is put are ignored."""

    task_class = (UI, 'RoundAgain')
    ports = 4


class StayOrShiftEnv(FrameRung):
    """Stay or Shift: Four ports, one a panel, in reading order.
    Presses before the question is put are ignored."""

    task_class = (UI, 'StayOrShift')
    ports = 4


class MovingPrizeEnv(FrameRung):
    """Moving Prize: Four ports, one a panel, the other way round from
    reading order. Presses before the question is put are ignored."""

    task_class = (UI, 'MovingPrize')
    ports = 4


ENVS = (NextInTurnEnv, RoundAgainEnv, StayOrShiftEnv, MovingPrizeEnv)

verify_next_in_turn_outcome = NextInTurnEnv.verifier()
verify_round_again_outcome = RoundAgainEnv.verifier()
verify_stay_or_shift_outcome = StayOrShiftEnv.verifier()
verify_moving_prize_outcome = MovingPrizeEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
