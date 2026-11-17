# -*- coding: utf-8 -*-
"""The stepped agent boundary for Which Block?.

Seventeen ports: 0-7 put a block on the machine or take it off; 8
runs it (a try); 9-16 name block 1-8 (both blocks, one after the
other, where two are needed).

Turn-based, so it takes the think clock: nothing moves until the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BlicketEnv(TaskEnv):
    """Deterministic, stepped view of one Which Block? run."""

    task_class = ('neural_workshop.ui.blicket', 'Blicket')
    ports = 17
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_which_block_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> BlicketEnv:
    """A production environment: the task's own defaults."""
    return BlicketEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_which_block_outcome = BlicketEnv.verifier()

__all__ = ['BlicketEnv', 'make_which_block_env',
           'verify_which_block_outcome']
