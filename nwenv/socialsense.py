# -*- coding: utf-8 -*-
"""The stepped agent boundary for Social Sense.

Eight ports. Port k picks answer k+1 of the buttons under the text. A chime
follows a right answer and a low note a wrong one.
From rung 13 two questions are asked about each situation, in turn.

Clocked: each item has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SocialSenseEnv(TaskEnv):
    """Deterministic, stepped view of one Social Sense run."""

    task_class = ('neural_workshop.ui.socialsense', 'SocialSense')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_social_sense_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> SocialSenseEnv:
    """A production environment: the task's own defaults."""
    return SocialSenseEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_social_sense_outcome = SocialSenseEnv.verifier()

__all__ = ['SocialSenseEnv', 'make_social_sense_env',
           'verify_social_sense_outcome']
