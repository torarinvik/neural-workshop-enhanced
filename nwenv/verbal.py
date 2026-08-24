# -*- coding: utf-8 -*-
"""The stepped agent boundary for Verbal Reasoning."""
from __future__ import annotations

from typing import Optional

from neural_workshop.verbal import MAX_CHOICES

from .taskenv import TaskEnv


class VerbalReasoningEnv(TaskEnv):
    """Five opaque answer ports over lazily read corpus questions."""

    task_class = ('neural_workshop.ui.verbal', 'VerbalReasoning')
    ports = MAX_CHOICES
    clocked = False
    action = 'choose'
    open_phase = ('asking',)
    settled_phase = ('judged',)
    knobs = {'trials': 'total_trials', 'show_explanation': 'show_explanation'}


def make_verbal_reasoning_env(seed: int = 0,
                              shm_name: Optional[str] = None
                              ) -> VerbalReasoningEnv:
    return VerbalReasoningEnv(seed=seed, shm_name=shm_name)


verify_verbal_reasoning_outcome = VerbalReasoningEnv.verifier()

__all__ = ['VerbalReasoningEnv', 'make_verbal_reasoning_env',
           'verify_verbal_reasoning_outcome']
