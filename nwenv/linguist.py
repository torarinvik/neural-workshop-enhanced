# -*- coding: utf-8 -*-
"""The stepped agent boundary for The Linguist.

Twelve ports. Ports 0-7 pick an answer (four, or six from rung 13).
When a sentence is to be built, ports 0-9 take a word tile, port 10
takes the last one back and port 11 says it is done. Green means the
right sentence or picture was picked, or a right sentence built.

Turn-based, so it takes the think clock: the page stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class LinguistEnv(TaskEnv):
    """Deterministic, stepped view of one The Linguist run."""

    task_class = ('neural_workshop.ui.linguist', 'Linguist')
    ports = 12
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_the_linguist_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> LinguistEnv:
    """A production environment: the task's own defaults."""
    return LinguistEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_the_linguist_outcome = LinguistEnv.verifier()

__all__ = ['LinguistEnv', 'make_the_linguist_env',
           'verify_the_linguist_outcome']
