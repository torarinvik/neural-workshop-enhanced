# -*- coding: utf-8 -*-
"""The stepped agent boundary for The Missing Word.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go. A caret
below a gap pressed offers four words for it, and one pressed goes in;
a word pressed offers to strike it out. Port 14 hands the passage in
and port 15 puts it back as dealt. The sounds are the same for a right
fix and a wrong one.

Clocked: the clock runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class MissingWordEnv(TaskEnv):
    """Deterministic, stepped view of one The Missing Word run."""

    task_class = ('neural_workshop.ui.missingword', 'MissingWord')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_missing_word_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> MissingWordEnv:
    """A production environment: the task's own defaults."""
    return MissingWordEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_missing_word_outcome = MissingWordEnv.verifier()

__all__ = ['MissingWordEnv', 'make_missing_word_env',
           'verify_missing_word_outcome']
