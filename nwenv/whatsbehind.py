# -*- coding: utf-8 -*-
"""The stepped agent boundary for What Is Behind.

Four ports: port k picks whole shape k, from the left.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhatsBehindEnv(TaskEnv):
    """Deterministic, stepped view of one What Is Behind run."""

    task_class = ('neural_workshop.ui.whatsbehind', 'WhatsBehind')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_whats_behind_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> WhatsBehindEnv:
    """A production environment: the task's own defaults."""
    return WhatsBehindEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_whats_behind_outcome = WhatsBehindEnv.verifier()

__all__ = ['WhatsBehindEnv', 'make_whats_behind_env',
           'verify_whats_behind_outcome']
