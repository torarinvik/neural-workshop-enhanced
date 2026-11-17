# -*- coding: utf-8 -*-
"""The stepped agent boundary for What Share.

Six ports: port k picks answer k (the shares rise from the left).

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhatShareEnv(TaskEnv):
    """Deterministic, stepped view of one What Share run."""

    task_class = ('neural_workshop.ui.whatshare', 'WhatShare')
    ports = 6
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_what_share_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> WhatShareEnv:
    """A production environment: the task's own defaults."""
    return WhatShareEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_what_share_outcome = WhatShareEnv.verifier()

__all__ = ['WhatShareEnv', 'make_what_share_env',
           'verify_what_share_outcome']
