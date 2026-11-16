# -*- coding: utf-8 -*-
"""The stepped agent boundary for Emotion.

Eight ports. Port k picks answer k+1 of the buttons under the face: the
emotion it shows (and from rung 14, after the strongest, the next
strongest). A chime follows a right answer and a low note a wrong one.

Clocked: each face has its own time, and it runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class EmotionEnv(TaskEnv):
    """Deterministic, stepped view of one Emotion run."""

    task_class = ('neural_workshop.ui.emotion', 'Emotion')
    ports = 8
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_emotion_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> EmotionEnv:
    """A production environment: the task's own defaults."""
    return EmotionEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_emotion_outcome = EmotionEnv.verifier()

__all__ = ['EmotionEnv', 'make_emotion_env',
           'verify_emotion_outcome']
