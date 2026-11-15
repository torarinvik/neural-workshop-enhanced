# -*- coding: utf-8 -*-
"""The stepped agent boundary for Same or Mirror?.

Five ports, one per answer: Same and Mirror for a pair of figures, up to
rung 12; one per figure in the row after that. A port past the answers
the trial offers does nothing. Green means the answer was right; there
is no par.

Turn-based, so it takes the think clock: the figures stand still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SameOrMirrorEnv(TaskEnv):
    """Deterministic, stepped view of one Same or Mirror? run."""

    task_class = ('neural_workshop.ui.mirror', 'SameOrMirror')
    ports = 5
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_same_or_mirror_env(seed: int = 0, shm_name: Optional[str] = None
                            ) -> SameOrMirrorEnv:
    """A production environment: the task's own defaults."""
    return SameOrMirrorEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_same_or_mirror_outcome = SameOrMirrorEnv.verifier()

__all__ = ['SameOrMirrorEnv', 'make_same_or_mirror_env',
           'verify_same_or_mirror_outcome']
