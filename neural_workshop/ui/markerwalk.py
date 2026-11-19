# -*- coding: utf-8 -*-
"""Marker Walk.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .ministeps import StepsTask


class MarkerWalk(StepsTask):
    """Marker Walk."""

    instance: Optional['MarkerWalk'] = None
    TITLE = 'Marker Walk'
    TASK_ID = 'marker_walk'
    PREFIX = 'MARKERWALK'
    KIND = 'walk'
