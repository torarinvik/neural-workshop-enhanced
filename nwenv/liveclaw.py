# -*- coding: utf-8 -*-
"""The stepped agent boundary for Live Claw Machine.

Six ports: 0-3 drive the gantry left, right, away and nearer for the
step they are sent in; 4 is the button, which lets the claw down; 5
walks round to the other window (front, right side). Green means a
prize went down the chute (the gold one, where only gold counts).

Clocked: the time at the stick runs, and the machine plays out, whether or not
the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class LiveClawEnv(TaskEnv):
    """Deterministic, stepped view of one Live Claw Machine run."""

    task_class = ('neural_workshop.ui.liveclaw', 'LiveClaw')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_live_claw_machine_env(seed: int = 0,
                                 shm_name: Optional[str] = None) -> LiveClawEnv:
    """A production environment: the task's own defaults."""
    return LiveClawEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_live_claw_machine_outcome = LiveClawEnv.verifier()

__all__ = ['LiveClawEnv', 'make_live_claw_machine_env',
           'verify_live_claw_machine_outcome']
