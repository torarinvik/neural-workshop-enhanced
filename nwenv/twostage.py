# -*- coding: utf-8 -*-
"""The stepped agent boundary for the forgiving walks in two stages.

Turn-based, as Long Way Round: nothing moves until a port is pressed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .longwalk import _Rung

UI = 'neural_workshop.ui.twostage'


class FetchAndCarryEnv(_Rung):
    """Fetch and Carry: Four ports: up, down, left, right. Green means
    the thing was carried onto the mark within the steps allowed."""

    task_class = (UI, 'FetchAndCarry')
    ports = 4


class PlateAndGateEnv(_Rung):
    """Plate and Gate: Four ports: up, down, left, right. Green means
    the goal was reached, through the gate the plate opens, within the
    steps allowed."""

    task_class = (UI, 'PlateAndGate')
    ports = 4


ENVS = (FetchAndCarryEnv, PlateAndGateEnv)

verify_fetch_and_carry_outcome = FetchAndCarryEnv.verifier()
verify_plate_and_gate_outcome = PlateAndGateEnv.verifier()

__all__ = [cls.__name__ for cls in ENVS]
