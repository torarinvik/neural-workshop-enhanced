# -*- coding: utf-8 -*-
"""Stepped agent boundary for the Go winning-move task."""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class GoEnv(TaskEnv):
    """One opaque port per board intersection."""

    task_class = ('neural_workshop.ui.go', 'GoWinningMove')
    ports = 19 * 19
    clocked = False
    action = 'answer'
    open_phase = ('solving',)
    settled_phase = ('solved', 'failed')
    knobs = {'difficulty': 'start_difficulty', 'trials': 'total_trials'}


def make_go_env(seed: int = 0, shm_name: Optional[str] = None) -> GoEnv:
    return GoEnv(seed=seed, shm_name=shm_name)


verify_go_outcome = GoEnv.verifier()

__all__ = ['GoEnv', 'make_go_env', 'verify_go_outcome']
