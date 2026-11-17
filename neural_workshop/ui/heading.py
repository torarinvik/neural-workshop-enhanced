# -*- coding: utf-8 -*-
"""Heading on screen: dots streaming out from the point headed for.

For the agent boundary: seven ports: port k picks mark k, from the left.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import heading as model
from ..i18n import _
from .scenetask import SceneShow


class Heading(SceneShow):
    """Heading."""

    instance: Optional['Heading'] = None

    TITLE = 'Heading'
    TASK_ID = 'heading'
    PREFIX = 'HEADING'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    SCENES = model
