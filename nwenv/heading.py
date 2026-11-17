# -*- coding: utf-8 -*-
"""The stepped agent boundary for Heading.

Seven ports: port k picks mark k, from the left.

Clocked: the scene plays and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HeadingEnv(TaskEnv):
    """Deterministic, stepped view of one Heading run."""

    task_class = ('neural_workshop.ui.heading', 'Heading')
    ports = 7
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_heading_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> HeadingEnv:
    """A production environment: the task's own defaults."""
    return HeadingEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_heading_outcome = HeadingEnv.verifier()

__all__ = ['HeadingEnv', 'make_heading_env',
           'verify_heading_outcome']
