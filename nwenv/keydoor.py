# -*- coding: utf-8 -*-
"""Key and Door.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .longwalk import _Rung


class KeyAndDoorEnv(_Rung):
    """Key and Door."""

    task_class = ('neural_workshop.ui.keydoor', 'KeyAndDoor')
    ports = 4


verify_key_and_door_outcome = KeyAndDoorEnv.verifier()

__all__ = ['KeyAndDoorEnv']
