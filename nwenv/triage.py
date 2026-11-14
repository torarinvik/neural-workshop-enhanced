# -*- coding: utf-8 -*-
"""The stepped agent boundary for Triage.

Seventeen ports. Ports 0-7 open cards one to eight (turning a face-down
card over costs a move; opening a turned one is free). Ports 8-15 swap
the open row's neighbours: the first and second digit, the second and
third, and so on. Port 16 is Done. A port for a card or a pair the round
does not have does nothing.

Green means the round earned at least par: what a pays-per-move
reference earned on the identical deal, less a share below rung twenty,
plus a share of the gap to the best possible choice past it.

Turn-based, so it takes the think clock -- which is the point: what is
being measured is what gets thought about.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

SWAP, DONE = 8, 16


class TriageEnv(TaskEnv):
    """Deterministic, stepped view of one Triage run."""

    task_class = ('neural_workshop.ui.triage', 'Triage')
    ports = 17
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_triage_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> TriageEnv:
    """A production environment: the task's own defaults."""
    return TriageEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_triage_outcome = TriageEnv.verifier()

__all__ = ['DONE', 'SWAP', 'TriageEnv', 'make_triage_env',
           'verify_triage_outcome']
