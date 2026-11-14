# -*- coding: utf-8 -*-
"""The stepped agent boundary for Signals.

Sixteen ports. Ports 0-7 pick objects one to eight when the partner has
spoken; ports 8-15 send glyphs one to eight when it is the player's turn
to speak (a two-glyph signal is two ports). A port that does not fit the
turn does nothing.

Green means the game understood at least par exchanges: what a learner
keeping a belief about every glyph understood on the identical game,
with ground given below rung twenty and asked for past it.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

GLYPH = 8


class SignalsEnv(TaskEnv):
    """Deterministic, stepped view of one Signals run."""

    task_class = ('neural_workshop.ui.signals', 'Signals')
    ports = 16
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_signals_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> SignalsEnv:
    """A production environment: the task's own defaults."""
    return SignalsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_signals_outcome = SignalsEnv.verifier()

__all__ = ['GLYPH', 'SignalsEnv', 'make_signals_env',
           'verify_signals_outcome']
