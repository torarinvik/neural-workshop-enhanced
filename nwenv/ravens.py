# -*- coding: utf-8 -*-
"""The stepped agent boundary for Matrix Reasoning.

Eight ports, one to a candidate. The easier half of the ladder offers
four, and on those rungs the top four ports do nothing — which the task
already refuses rather than the boundary guessing at, and which the
learner has as much to discover as anything else here.

Turn-based: the grid does not move, and a puzzle waits as long as it is
left. The exposure option, which takes the matrix away after a while and
makes it a memory task as well as a reasoning one, still runs — but off
the driver's clock rather than the wall's, so a stepped run's exposure is
the same number of frames every time it is replayed.

Feedback is forced on. A player may turn it off to go faster, knowing
perfectly well how they did; a learner whose whole payment is that label
may not.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class MatrixReasoningEnv(TaskEnv):
    """Deterministic, stepped view of one Matrix Reasoning run."""

    task_class = ('neural_workshop.ui.ravens', 'MatrixReasoning')
    ports = 8
    clocked = True
    action = 'answer'
    open_phase = ('asking', 'hidden')
    settled_phase = ('feedback',)
    knobs = {'rung': 'start_level', 'trials': 'total_trials',
             'exposure_ms': 'exposure_ms', 'adaptive': 'adaptive'}
    requires = {'feedback': True}


def make_ravens_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> MatrixReasoningEnv:
    """A production environment: the task's own defaults."""
    return MatrixReasoningEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_ravens_outcome = MatrixReasoningEnv.verifier()

__all__ = ['MatrixReasoningEnv', 'make_ravens_env', 'verify_ravens_outcome']
