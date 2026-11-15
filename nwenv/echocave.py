# -*- coding: utf-8 -*-
"""The stepped agent boundary for Echo Cave.

Nine ports: 0-7 steer the bat for the step they are sent in (up,
down, left, right, then up-left, up-right, down-left, down-right); 8
clicks. Echoes of a click and the moths' buzzing reach the agent as
sound. Green means the bat got out of the cave without touching rock,
with enough moths.

Clocked: the bat flies on whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class EchoCaveEnv(TaskEnv):
    """Deterministic, stepped view of one Echo Cave run."""

    task_class = ('neural_workshop.ui.echocave', 'EchoCave')
    ports = 9
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_echo_cave_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> EchoCaveEnv:
    """A production environment: the task's own defaults."""
    return EchoCaveEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_echo_cave_outcome = EchoCaveEnv.verifier()

__all__ = ['EchoCaveEnv', 'make_echo_cave_env',
           'verify_echo_cave_outcome']
