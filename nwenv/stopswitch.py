# -*- coding: utf-8 -*-
"""The stepped agent boundary for Stop & Switch.

Two ports: answer left, answer right. Doing nothing is the answer to a
stop signal. A trial is a block of stimuli; green means enough of them
were answered right -- in time, by the rule in force, and not at all
when a stop signal came.

Clocked: the time to answer is part of the task, and the stop signal
arrives a fixed time after the stimulus.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class StopAndSwitchEnv(TaskEnv):
    """Deterministic, stepped view of one Stop & Switch run."""

    task_class = ('neural_workshop.ui.stopswitch', 'StopAndSwitch')
    ports = 2
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_stop_and_switch_env(seed: int = 0, shm_name: Optional[str] = None
                             ) -> StopAndSwitchEnv:
    """A production environment: the task's own defaults."""
    return StopAndSwitchEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_stop_and_switch_outcome = StopAndSwitchEnv.verifier()

__all__ = ['StopAndSwitchEnv', 'make_stop_and_switch_env',
           'verify_stop_and_switch_outcome']
