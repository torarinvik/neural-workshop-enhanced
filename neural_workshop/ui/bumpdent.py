# -*- coding: utf-8 -*-
"""Bump or Dent on screen: shaded round marks, a lamp or a labelled bump.

For the agent boundary: ten ports: 0 says bump and 1 dent; where the question is how many
are bumps, port k answers k.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .. import bumpdent as model
from ..i18n import _
from .scenetask import SceneChoice


class BumpDent(SceneChoice):
    """Bump or Dent."""

    instance: Optional['BumpDent'] = None

    TITLE = 'Bump or Dent'
    TASK_ID = 'bump_or_dent'
    PREFIX = 'BUMPDENT'
    CATEGORY = 'perception'
    FOOTNOTE = _('click an answer or press its number   Esc: menu')
    MODEL = model
