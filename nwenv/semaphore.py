# -*- coding: utf-8 -*-
"""The stepped agent boundary for Semaphore.

Forty ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-39 are the letters A to Z. A press on the tip of one of your
flags takes hold of it, and it follows the pointer round until the
button is let go. A letter counts when your flags copy the signal and
the letter typed is the one it stands for. The agent hears a bell at
each new signal.

Clocked: the signaller moves on whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SemaphoreEnv(TaskEnv):
    """Deterministic, stepped view of one Semaphore run."""

    task_class = ('neural_workshop.ui.semaphore', 'Semaphore')
    ports = 40
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_semaphore_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> SemaphoreEnv:
    """A production environment: the task's own defaults."""
    return SemaphoreEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_semaphore_outcome = SemaphoreEnv.verifier()

__all__ = ['SemaphoreEnv', 'make_semaphore_env',
           'verify_semaphore_outcome']
