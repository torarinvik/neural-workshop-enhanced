# -*- coding: utf-8 -*-
"""The stepped agent boundary for Numberology."""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

KEYS = '0123456789-'
BACK, SUBMIT = len(KEYS), len(KEYS) + 1


class NumberologyEnv(TaskEnv):
    """Opaque typewriter ports for the next-number sequence game."""

    task_class = ('neural_workshop.ui.numberology', 'Numberology')
    ports = SUBMIT + 1
    clocked = False
    open_phase = ('working',)
    settled_phase = ('judged',)
    knobs = {'difficulty': 'start_difficulty', 'trials': 'total_trials'}

    def drive(self, task: Any, port: int) -> None:
        if port < len(KEYS):
            task.write(KEYS[port])
        elif port == BACK:
            task.erase()
        elif port == SUBMIT:
            task.submit()


def make_numberology_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> NumberologyEnv:
    return NumberologyEnv(seed=seed, shm_name=shm_name)


verify_numberology_outcome = NumberologyEnv.verifier()

__all__ = ['KEYS', 'NumberologyEnv', 'make_numberology_env',
           'verify_numberology_outcome']
