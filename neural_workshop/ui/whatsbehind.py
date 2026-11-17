# -*- coding: utf-8 -*-
"""What Is Behind on screen: a shape behind a screen and whole shapes below.

For the agent boundary: four ports: port k picks whole shape k, from the left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import whatsbehind as model
from ..i18n import _
from .scenetask import SceneChoice


class WhatsBehind(SceneChoice):
    """What Is Behind."""

    instance: Optional['WhatsBehind'] = None

    TITLE = 'What Is Behind'
    TASK_ID = 'whats_behind'
    PREFIX = 'WHATSBEHIND'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
