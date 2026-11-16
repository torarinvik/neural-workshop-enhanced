# -*- coding: utf-8 -*-
"""The stepped agent boundary for Full Stop.

Sixteen ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go. A word
pressed puts a full stop after it, or takes it away. Port 14 hands the
stops in and port 15 takes them all away. The sounds say whether a stop
went in or came out, never whether it was right.

Clocked: the clock runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FullStopEnv(TaskEnv):
    """Deterministic, stepped view of one Full Stop run."""

    task_class = ('neural_workshop.ui.fullstop', 'FullStop')
    ports = 16
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_full_stop_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> FullStopEnv:
    """A production environment: the task's own defaults."""
    return FullStopEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_full_stop_outcome = FullStopEnv.verifier()

__all__ = ['FullStopEnv', 'make_full_stop_env',
           'verify_full_stop_outcome']
