# -*- coding: utf-8 -*-
"""Everything drawn on screen.

``message`` / ``menu`` / ``textinput``
    Reusable pieces: a modal notice, the generic menu with its value
    cyclers, and a one-line text prompt.
``screens`` / ``gameselect`` / ``taskhub``
    The concrete menu screens, plus the category task hub.
``monkeyladder`` / ``ncupmonte``
    Standalone working-memory and misc tasks launched from the hub.
``taskoptions`` / ``cursor``
    The per-task settings screens reached with C, and the pointing-hand
    cursor the mouse-driven screens wear.
``field``
    The board and the stimuli on it.
``hud`` / ``trialui`` / ``readouts``
    Labels: the permanent furniture, the ones belonging to a trial in
    progress, and the ones reporting past performance.
``graph`` / ``effects``
    The progress chart, and the two full-screen extras.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations
