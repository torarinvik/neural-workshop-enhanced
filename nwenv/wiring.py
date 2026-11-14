# -*- coding: utf-8 -*-
"""The stepped agent boundary for Hidden Wiring.

Eleven ports. The first eight flip switches one to eight, which costs
nothing; a port for a switch the rung has not put out does nothing. Then
Look, which shows the lamps for the switches as they stand and costs a
point; Exam; and Answer, which gives the switches as they stand for the
pattern the exam is showing.

Green means looks plus penalties came to no more than par: what a
reference that keeps every wiring still possible, and looks where those
wirings split most, paid on the identical deal -- the same lies on the
same numbered look -- scaled by the rung, below it past rung twenty.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: Flip a switch: ports 0-7. Then these.
LOOK, EXAM, ANSWER = 8, 9, 10


class WiringEnv(TaskEnv):
    """Deterministic, stepped view of one Hidden Wiring run."""

    task_class = ('neural_workshop.ui.wiring', 'Wiring')
    ports = 11
    clocked = False
    action = 'steer'
    open_phase = ('looking', 'examining')
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_wiring_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> WiringEnv:
    """A production environment: the task's own defaults."""
    return WiringEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_wiring_outcome = WiringEnv.verifier()

__all__ = ['ANSWER', 'EXAM', 'LOOK', 'WiringEnv', 'make_wiring_env',
           'verify_wiring_outcome']
