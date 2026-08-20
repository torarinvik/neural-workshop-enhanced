# -*- coding: utf-8 -*-
"""Everything drawn on screen.

``message`` / ``menu`` / ``textinput``
    Reusable pieces: a modal notice, the generic menu with its value
    cyclers, and a one-line text prompt.
``screens`` / ``gameselect`` / ``taskhub``
    The concrete menu screens, plus the category task hub.
``monkeyladder`` / ``ncupmonte``
    Standalone working-memory and misc tasks launched from the hub.
``concentration`` / ``recognition``
    The long-term-memory games, drawing on the downloaded media
    libraries in :mod:`neural_workshop.datasets`.
``reflex``
    The attention task. The one screen here that animates, so it keeps
    its sprites between frames rather than rebuilding them.
``counting``
    The perception task. Generates its own shapes, so it needs no
    downloaded media.
``graphmapping``
    The reasoning task. Its graph arithmetic — building networks,
    rewiring them and deciding whether two are the same — is free
    functions at the top of the module, testable without a window.
``ravens``
    The other reasoning task: Raven's-style matrices. The puzzles come
    from :mod:`neural_workshop.ravens`, which needs no window; this
    module only draws them and takes the answer.
``taskoptions`` / ``cursor``
    The per-task settings screens reached with C, and the pointing-hand
    cursor the mouse-driven screens wear. A spec may carry a *note*: a
    line rebuilt from the rows on every change, for saying what a
    combination of them does when no single row can.
``field``
    The board and the stimuli on it.
``hud`` / ``trialui`` / ``readouts``
    Labels: the permanent furniture, the ones belonging to a trial in
    progress, and the ones reporting past performance.
``graph`` / ``effects``
    The progress chart, and the saccadic eye exercise.

Every screen here that pushes its own ``on_draw`` is an *overlay*: it
registers with :mod:`neural_workshop.display` while it is open, offers
``relayout()``, and calls ``display.ensure_laid_out()`` before drawing,
so a window resize reaches it too.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations
