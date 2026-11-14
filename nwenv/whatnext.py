# -*- coding: utf-8 -*-
"""The stepped agent boundary for What Happens Next.

Six ports, one to an option; a port past the options the rung puts out
does nothing. Green means the true continuation was chosen.

Clocked, because the evidence is motion: an opening and its endings
that were never seen playing are a row of still pictures, and the
decoy played backwards is the same pictures in a different order.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class WhatNextEnv(TaskEnv):
    """Deterministic, stepped view of one What Happens Next run."""

    task_class = ('neural_workshop.ui.whatnext', 'WhatNext')
    ports = 6
    clocked = True
    action = 'steer'
    open_phase = ('choosing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_what_next_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> WhatNextEnv:
    """A production environment: the task's own defaults."""
    return WhatNextEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_what_next_outcome = WhatNextEnv.verifier()

__all__ = ['WhatNextEnv', 'make_what_next_env', 'verify_what_next_outcome']
