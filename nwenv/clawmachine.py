# -*- coding: utf-8 -*-
"""The stepped agent boundary for Claw Machine.

Five ports: 0-3 move the trolley left, right, in and out for the step;
4 drops the claw. Green means the claw closed on the gold prize.

Clocked: the claw swings and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ClawMachineEnv(TaskEnv):
    """Deterministic, stepped view of one Claw Machine run."""

    task_class = ('neural_workshop.ui.clawmachine', 'ClawMachine')
    ports = 5
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_claw_machine_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> ClawMachineEnv:
    """A production environment: the task's own defaults."""
    return ClawMachineEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_claw_machine_outcome = ClawMachineEnv.verifier()

__all__ = ['ClawMachineEnv', 'make_claw_machine_env',
           'verify_claw_machine_outcome']
