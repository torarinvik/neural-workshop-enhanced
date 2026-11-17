# -*- coding: utf-8 -*-
"""Parallel? on screen: two long lines, hatched higher up.

For the agent boundary: two ports: 0 says parallel, 1 not.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import parallel as model
from ..i18n import _
from .scenetask import SceneChoice


class Parallel(SceneChoice):
    """Parallel?."""

    instance: Optional['Parallel'] = None

    TITLE = 'Parallel?'
    TASK_ID = 'parallel'
    PREFIX = 'PARALLEL'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
