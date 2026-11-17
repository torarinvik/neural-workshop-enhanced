# -*- coding: utf-8 -*-
"""The stepped agent boundary for Up or Down.

Three ports: 0 says up and 1 down; with three tones, port k says
tone k was the highest. The tones reach the agent only as sound.

Clocked: the sounds play and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class UpOrDownEnv(TaskEnv):
    """Deterministic, stepped view of one Up or Down run."""

    task_class = ('neural_workshop.ui.upordown', 'UpOrDown')
    ports = 3
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_up_or_down_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> UpOrDownEnv:
    """A production environment: the task's own defaults."""
    return UpOrDownEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_up_or_down_outcome = UpOrDownEnv.verifier()

__all__ = ['UpOrDownEnv', 'make_up_or_down_env',
           'verify_up_or_down_outcome']
